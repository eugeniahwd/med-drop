"""Aplikasi FastAPI MedDrop: route API dan penyajian frontend statis.

Jalankan dari root proyek:
    python -m backend.main

Endpoint admin tidak memakai autentikasi karena ini prototipe simulasi lokal.
"""

import math
import threading
import uuid

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles

from backend import schemas
from backend.barcode_reader import read_barcode
from backend.classifier import Classifier, load_classifier
from backend.config import ROOT_DIR, load_classes, load_config
from backend.db import Database, now_wib
from backend.decision import REASON_TEXTS, decide
from backend.items import PHOTO_DIRS, load_items

APP_NAME = "MedDrop"
FRONTEND_DIR = ROOT_DIR / "frontend"
UPLOADS_DIR = ROOT_DIR / "uploads"
BARCODE_DIR = ROOT_DIR / "data" / "barcodes"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def create_app(config: dict | None = None, db: Database | None = None, classifier: Classifier | None = None,
               classes: list | None = None, uploads_dir=UPLOADS_DIR) -> FastAPI:
    cfg = config if config is not None else load_config()
    classes = classes if classes is not None else load_classes()
    db = db or Database()
    if not db.path.exists():
        raise RuntimeError(f"Database {db.path} belum ada. Jalankan dulu: python scripts/seed_db.py")
    classifier = classifier or load_classifier(cfg, classes)
    items = load_items()
    daily_limit = cfg["points"]["daily_limit_deposits"]
    # Satu verifikasi pada satu waktu, agar cek kuota dan pencatatan tidak saling mendahului.
    verify_lock = threading.Lock()

    app = FastAPI(title="MedDrop API", description="Prototipe simulasi. Bukan alat medis.")
    app.state.config = cfg

    def member_state(token: str) -> dict:
        if db.get_member(token) is None:
            raise HTTPException(404, "Nomor member tidak dikenal.")
        state = db.get_member_state(token)
        return {**state, "daily_limit": daily_limit,
                "remaining_today": max(daily_limit - state["deposits_today"], 0)}

    def bin_state(bin_id: str) -> dict:
        b = db.get_bin(bin_id)
        if b is None:
            raise HTTPException(404, f"Bin {bin_id} tidak dikenal.")
        return {**b, "accepting": b["fill_pct"] < 100}

    # ---------- untuk kios ----------

    @app.get("/api/config")
    def get_config():
        clf = cfg["classifier"]
        return {
            "app_name": APP_NAME,
            "classifier": {
                "backend": clf["backend"],
                "is_mock": classifier.is_mock,
                "threshold_with_barcode": clf["threshold_with_barcode"],
                "threshold_photo_only": clf["threshold_photo_only"],
                "min_confidence_floor": clf["min_confidence_floor"],
            },
            "weight": cfg["weight"],
            "points": cfg["points"],
            "bin": cfg["bin"],
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
        if not math.isfinite(weight_g):
            raise HTTPException(422, "Berat tidak valid.")
        # Pemeriksaan sebelum pintu dibuka: tidak dicatat sebagai transaksi.
        member_state(member_token)
        if not bin_state(bin_id)["accepting"]:
            raise HTTPException(409, "Mesin penuh, silakan setor di lokasi lain.")

        photo_bytes = _read_upload(photo)
        if cv2.imdecode(np.frombuffer(photo_bytes, np.uint8), cv2.IMREAD_COLOR) is None:
            raise HTTPException(422, "Foto tidak dapat dibaca.")
        barcode_bytes = _read_upload(barcode_image) if barcode_image is not None else None

        barcode_result = read_barcode(barcode_bytes, barcode_text)
        photo_pred = classifier.predict(photo_bytes)
        now = now_wib()
        photo_path = _save_photo(uploads_dir, photo_bytes, now)

        with verify_lock:
            result = decide(db.get_member_state(member_token), photo_pred, barcode_result, weight_g,
                            cfg, db.get_products(), classes)
            barcode_signal = result["signals"]["barcode"]
            transaction_id = db.record_attempt(
                {
                    "ts": now,
                    "bin_id": bin_id,
                    "member_token": member_token,
                    "claimed_product_id": barcode_signal["product_id"],
                    "photo_class": photo_pred["class_id"],
                    "photo_conf": photo_pred["confidence"],
                    "barcode_present": barcode_signal["present"],
                    "barcode_valid": bool(barcode_signal["valid"]),
                    "weight_g": weight_g,
                    "decision": result["decision"],
                    "reason_code": result["reason_code"],
                    "photo_path": photo_path,
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

    # ---------- untuk dashboard admin ----------

    @app.get("/api/admin/transactions", response_model=list[schemas.Transaction])
    def get_transactions(
        decision: str | None = Query(None, pattern="^(ACCEPT|REJECT)$"),
        reason_code: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
    ):
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
                {"reason_code": code, "count": rejected.get(code, 0)}
                for code in REASON_TEXTS if code != "OK"
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
        return db.create_alert(bin_id, "TAMPER", "Simulasi: pintu bin dibuka paksa")

    # ---------- berkas statis ----------
    # Foto kartu hanya dari split test, plus gambar barcode dummy.
    for url_prefix, directory in PHOTO_DIRS.items():
        app.mount(url_prefix, StaticFiles(directory=directory, check_dir=False), name=url_prefix.strip("/"))
    app.mount("/media/barcodes", StaticFiles(directory=BARCODE_DIR, check_dir=False), name="barcodes")
    # Dipasang terakhir agar route di atas tetap didahulukan.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


def _read_upload(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Berkas terlalu besar (maksimum 10 MB).")
    return data


def _save_photo(uploads_dir, photo_bytes: bytes, now) -> str:
    """Simpan foto setoran untuk audit. Mengembalikan path relatif 'uploads/...'."""
    if photo_bytes.startswith(b"\x89PNG"):
        ext = ".png"
    elif photo_bytes.startswith(b"\xff\xd8"):
        ext = ".jpg"
    else:
        ext = ".img"
    day = now.strftime("%Y%m%d")
    name = f"{now:%H%M%S}_{uuid.uuid4().hex[:8]}{ext}"
    target = uploads_dir / day
    target.mkdir(parents=True, exist_ok=True)
    (target / name).write_bytes(photo_bytes)
    return f"uploads/{day}/{name}"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:create_app", factory=True, host="127.0.0.1", port=8000)
