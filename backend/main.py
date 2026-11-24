"""Aplikasi FastAPI MedDrop: route API dan penyajian frontend.

Jalankan dari root proyek:
    python -m backend.main

Endpoint admin tidak memakai login karena ini simulasi lokal.
"""

import math
import os
import socket
import uuid

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles

from backend import cloud, schemas
from backend.barcode_reader import read_barcode
from backend.classifier import load_classifier
from backend.config import ROOT_DIR, load_classes, load_config, load_env
from backend.db import Database, now_wib
from backend.decision import REASON_TEXTS, decide
from backend.items import load_items
from backend.seed import DEMO_BIN, load_seed_files

UPLOADS_DIR = ROOT_DIR / "uploads"


def create_app(config=None, db=None, classifier=None, classes=None, uploads_dir=UPLOADS_DIR):
    load_env()
    cfg = config or load_config()
    classes = classes or load_classes()
    db = db or Database()
    if not db.path.exists():
        raise RuntimeError("Database belum ada. Jalankan dulu: python scripts/seed_db.py")
    classifier = classifier or load_classifier(cfg, classes)
    items = load_items()
    demo_members = load_seed_files()[1]
    daily_limit = cfg["points"]["daily_limit_deposits"]

    app = FastAPI(title="MedDrop API", description="Simulation prototype. Not a medical device.")

    def member_state(token):
        if db.get_member(token) is None:
            raise HTTPException(404, "Member number not recognized.")
        state = db.get_member_state(token)
        return {**state, "daily_limit": daily_limit,
                "remaining_today": max(daily_limit - state["deposits_today"], 0)}

    def bin_state(bin_id):
        b = db.get_bin(bin_id)
        if b is None:
            raise HTTPException(404, f"Unknown bin {bin_id}.")
        return {**b, "accepting": b["fill_pct"] < 100}

    # ---------- untuk kios ----------

    @app.get("/api/config")
    def get_config():
        return {
            "classifier": {**cfg["classifier"], "is_mock": classifier.is_mock},
            "weight": cfg["weight"],
            "points": cfg["points"],
            "bin": cfg["bin"],
            "machine_bin_id": DEMO_BIN["bin_id"],
            "demo_members": [{"token": m["token"], "demo_role": m["demo_role"]} for m in demo_members],
            "classes": [{"class_id": c["class_id"], "display": c["display"]} for c in classes],
            "products": [{"product_id": p["product_id"], "display": p["display"], "barcode": p["barcode"]}
                         for p in db.get_products().values()],
        }

    @app.get("/api/items", response_model=list[schemas.Item])
    def get_items():
        return items

    @app.get("/api/members/{token}", response_model=schemas.MemberState)
    def get_member(token: str):
        return member_state(token)

    @app.get("/api/bins/{bin_id}", response_model=schemas.BinState)
    def get_bin(bin_id: str):
        return bin_state(bin_id)

    @app.post("/api/verify", response_model=schemas.VerifyResponse)
    def verify(
        member_token: str = Form(...),
        bin_id: str = Form(...),
        weight_g: float = Form(...),
        photo: UploadFile = File(...),
        barcode_image: UploadFile | None = File(None),
        barcode_text: str | None = Form(None),
    ):
        barcode_bytes = barcode_image.file.read() if barcode_image else None
        return run_verify(member_token, bin_id, weight_g, photo.file.read(), barcode_bytes, barcode_text)

    def run_verify(member_token, bin_id, weight_g, photo_bytes, barcode_bytes, barcode_text):
        """Dipakai web simulasi (/api/verify) dan ESP32 (/api/device/verify)."""
        if not math.isfinite(weight_g):
            raise HTTPException(422, "Invalid weight reading.")
        # Dicek sebelum pintu dibuka, jadi tidak dicatat sebagai transaksi.
        member_state(member_token)
        if not bin_state(bin_id)["accepting"]:
            raise HTTPException(409, "This machine is full. Please use another drop-off point.")
        if cv2.imdecode(np.frombuffer(photo_bytes, np.uint8), cv2.IMREAD_COLOR) is None:
            raise HTTPException(422, "The photo could not be read.")

        barcode_result = read_barcode(barcode_bytes, barcode_text)
        photo_pred = classifier.predict(photo_bytes)
        result = decide(db.get_member_state(member_token), photo_pred, barcode_result, weight_g,
                        cfg, db.get_products(), classes)

        now = now_wib()
        barcode = result["signals"]["barcode"]
        transaction_id = db.record_attempt(
            {
                "ts": now,
                "bin_id": bin_id,
                "member_token": member_token,
                "claimed_product_id": barcode["product_id"],
                "photo_class": photo_pred["class_id"],
                "photo_conf": photo_pred["confidence"],
                "barcode_present": barcode["present"],
                "barcode_valid": bool(barcode["valid"]),
                "weight_g": weight_g,
                "decision": result["decision"],
                "reason_code": result["reason_code"],
                "photo_path": save_photo(uploads_dir, photo_bytes, now),
            },
            points=result["points_awarded"],
            alert_fill_pct=cfg["bin"]["alert_fill_pct"],
        )

        return {
            "decision": result["decision"],
            "reason_code": result["reason_code"],
            "reason_text": result["reason_text"],
            "signals": result["signals"],
            "points_awarded": result["points_awarded"],
            "member": member_state(member_token),
            "transaction_id": transaction_id,
            "bin": bin_state(bin_id),
        }

    # ---------- untuk ESP32 (perangkat asli) ----------

    def check_device_key(key):
        expected = os.environ.get("DEVICE_KEY", "")
        if not expected or key != expected:
            raise HTTPException(401, "Unknown device key.")

    @app.post("/api/device/heartbeat")
    def device_heartbeat(beat: schemas.Heartbeat, x_device_key: str = Header("")):
        check_device_key(x_device_key)
        return {"ok": True, "saved_to_cloud": cloud.save_heartbeat(**beat.model_dump())}

    @app.post("/api/device/verify")
    def device_verify(
        member_token: str = Form(...),
        bin_id: str = Form(...),
        weight_g: float = Form(...),
        photo: UploadFile = File(...),
        barcode_text: str | None = Form(None),
        x_device_key: str = Header(""),
    ):
        check_device_key(x_device_key)
        result = run_verify(member_token, bin_id, weight_g, photo.file.read(), None, barcode_text)
        photo_signal = result["signals"]["photo"]
        cloud.save_transaction({
            "device_id": bin_id,
            "member_token": member_token,
            "barcode": result["signals"]["barcode"]["decoded"],
            "weight_g": weight_g,
            "photo_class": photo_signal["class_id"],
            "photo_conf": photo_signal["confidence"],
            "decision": result["decision"],
            "reason_code": result["reason_code"],
            "points_awarded": result["points_awarded"],
        })
        # Jawaban ringkas supaya mudah dibaca ESP32.
        return {
            "decision": result["decision"],
            "reason_code": result["reason_code"],
            "reason_text": result["reason_text"],
            "product": photo_signal["display"],
            "confidence": photo_signal["confidence"],
            "points_awarded": result["points_awarded"],
            "points_total": result["member"]["points_total"],
        }

    # ---------- untuk dashboard admin ----------

    @app.get("/api/admin/transactions", response_model=list[schemas.Transaction])
    def get_transactions(decision: str | None = None, reason_code: str | None = None,
                         limit: int = Query(200, ge=1, le=1000)):
        return db.list_transactions(limit=limit, decision=decision, reason_code=reason_code)

    @app.get("/api/admin/stats", response_model=schemas.Stats)
    def get_stats():
        accepted = db.accepted_count_by_photo_class()
        rejected = db.rejected_count_by_reason()
        return {
            "totals": db.transaction_totals(),
            "accepted_by_product": [
                {"class_id": c["class_id"], "product_id": c["product_id"], "display": c["display"],
                 "count": accepted.get(c["class_id"], 0)}
                for c in classes if c["kind"] == "product"
            ],
            "rejected_by_reason": [
                {"reason_code": code, "count": rejected.get(code, 0)} for code in REASON_TEXTS if code != "OK"
            ],
            "bins": [bin_state(b["bin_id"]) for b in db.list_bins()],
        }

    @app.get("/api/admin/alerts", response_model=list[schemas.Alert])
    def get_alerts():
        return db.list_alerts()

    @app.post("/api/admin/bins/{bin_id}/empty", response_model=schemas.BinState)
    def empty_bin(bin_id: str):
        bin_state(bin_id)
        db.empty_bin(bin_id)
        return bin_state(bin_id)

    @app.post("/api/admin/bins/{bin_id}/tamper", response_model=schemas.Alert)
    def tamper_bin(bin_id: str):
        bin_state(bin_id)
        return db.create_alert(bin_id, "TAMPER", "Simulated forced opening of the bin door")

    # ---------- file statis ----------
    app.mount("/media/test", StaticFiles(directory=ROOT_DIR / "dataset" / "test", check_dir=False))
    app.mount("/media/test_degraded", StaticFiles(directory=ROOT_DIR / "dataset" / "test_degraded", check_dir=False))
    app.mount("/media/barcodes", StaticFiles(directory=ROOT_DIR / "data" / "barcodes", check_dir=False))
    app.mount("/", StaticFiles(directory=ROOT_DIR / "frontend", html=True))  # paling akhir
    return app


def save_photo(uploads_dir, photo_bytes, now):
    """Simpan foto setoran untuk audit, kembalikan path relatif."""
    folder = uploads_dir / now.strftime("%Y%m%d")
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{now:%H%M%S}_{uuid.uuid4().hex[:6]}.jpg"
    (folder / name).write_bytes(photo_bytes)
    return f"uploads/{folder.name}/{name}"


def lan_ip():
    """IP laptop di jaringan Wi-Fi (untuk SERVER_URL di firmware ESP32). Tidak mengirim data apa pun."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


if __name__ == "__main__":
    import uvicorn

    print(f"Web simulasi: http://127.0.0.1:8000   |   untuk ESP32: http://{lan_ip()}:8000")
    # 0.0.0.0 supaya ESP32 di Wi-Fi yang sama bisa mengakses server ini.
    uvicorn.run("backend.main:create_app", factory=True, host="0.0.0.0", port=8000)
