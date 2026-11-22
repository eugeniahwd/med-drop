"""Isi data awal: produk, anggota fiktif, dan satu bin. Dipakai scripts/seed_db.py dan tes.

MBR-0003 diberi setoran contoh hari ini sampai batas harian supaya penolakan
QUOTA bisa didemokan. Setoran contoh ini data demo (photo_path kosong).
"""

import json

from backend.config import ROOT_DIR
from backend.db import Database, now_wib

DATA_DIR = ROOT_DIR / "data"
DEMO_BIN = {"bin_id": "BIN-001", "location": "Partner pharmacy lobby (simulated)"}


def load_seed_files():
    """(produk, anggota) dari data/*.seed.json."""
    products = json.loads((DATA_DIR / "products.seed.json").read_text(encoding="utf-8"))["products"]
    members = json.loads((DATA_DIR / "members.seed.json").read_text(encoding="utf-8"))["members"]
    return products, members


def seed(db: Database, cfg: dict, classes: list, products: list, members: list) -> dict:
    """Isi database. Aman dijalankan berulang. Mengembalikan {token: jumlah setoran contoh}."""
    db.init_schema()
    for product in products:
        db.upsert_product(product)
    for member in members:
        db.upsert_member(member["token"], now_wib())
    db.upsert_bin(DEMO_BIN["bin_id"], DEMO_BIN["location"], cfg["bin"]["capacity_g"])
    return {m["token"]: fill_daily_limit(db, m["token"], cfg, classes, products)
            for m in members if m.get("seed_at_daily_limit")}


def fill_daily_limit(db: Database, token: str, cfg: dict, classes: list, products: list) -> int:
    """Tambah setoran contoh hari ini sampai anggota mencapai batas harian."""
    missing = cfg["points"]["daily_limit_deposits"] - db.get_member_state(token)["deposits_today"]
    class_of = {c["product_id"]: c["class_id"] for c in classes if c["kind"] == "product"}
    for i in range(max(missing, 0)):
        product = products[i % len(products)]
        db.record_attempt(
            {
                "ts": now_wib(),
                "bin_id": DEMO_BIN["bin_id"],
                "member_token": token,
                "claimed_product_id": product["product_id"],
                "photo_class": class_of[product["product_id"]],
                "photo_conf": None,
                "barcode_present": True,
                "barcode_valid": True,
                "weight_g": (product["tare_g"] + product["gross_g"]) / 2,
                "decision": "ACCEPT",
                "reason_code": "OK",
                "photo_path": None,
            },
            points=cfg["points"]["per_valid_deposit"],
            alert_fill_pct=cfg["bin"]["alert_fill_pct"],
        )
    return max(missing, 0)
