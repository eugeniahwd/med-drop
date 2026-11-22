"""Mengisi database: produk, anggota fiktif, dan satu bin.

    python scripts/seed_db.py           # buat/lengkapi database; transaksi lama dipertahankan
    python scripts/seed_db.py --reset   # hapus database lalu buat ulang dari nol

Anggota bertanda `seed_at_daily_limit` (MBR-0003) diberi setoran contoh hari
ini sampai batas harian di config.yaml, supaya penolakan QUOTA bisa didemokan.
Setoran contoh ini adalah DATA DEMO dan bisa dikenali dari photo_path dan
photo_conf yang kosong. Batas dihitung per hari (WIB), jadi jalankan ulang skrip
ini pada hari demo.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import ean13  # noqa: E402
from backend.config import load_config  # noqa: E402
from backend.db import DEFAULT_DB_PATH, Database, now_wib  # noqa: E402

DATA_DIR = ROOT / "data"
DEMO_BIN = {"bin_id": "BIN-001", "location": "Lobi apotek mitra (simulasi)"}


def load_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def check_seed_data(classes: list, products: list) -> list[str]:
    errors = []
    product_ids = [p["product_id"] for p in products]
    barcodes = [p["barcode"] for p in products]
    if len(set(product_ids)) != len(product_ids):
        errors.append("Ada product_id ganda di products.seed.json")
    if len(set(barcodes)) != len(barcodes):
        errors.append("Ada barcode ganda di products.seed.json")
    for p in products:
        if not ean13.is_dummy(p["barcode"]):
            errors.append(f"Barcode {p['product_id']} ({p['barcode']!r}) bukan EAN-13 dummy valid "
                          "(harus 13 digit, digit cek benar, berawalan 2)")
        if not 0 <= p["weight_min_g"] < p["weight_max_g"]:
            errors.append(f"Kisaran berat {p['product_id']} tidak valid")
    for c in classes:
        if c["kind"] == "product" and c.get("product_id") not in product_ids:
            errors.append(f"Kelas {c['class_id']} menunjuk product_id {c.get('product_id')!r} "
                          "yang tidak ada di products.seed.json")
    return errors


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
                "weight_g": (product["weight_min_g"] + product["weight_max_g"]) / 2,
                "decision": "ACCEPT",
                "reason_code": "OK",
                "photo_path": None,
            },
            points=cfg["points"]["per_valid_deposit"],
            alert_fill_pct=cfg["bin"]["alert_fill_pct"],
        )
    return max(missing, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="hapus database lalu buat ulang dari nol")
    args = parser.parse_args()

    cfg = load_config()
    classes = load_json("classes.json")
    products = load_json("products.seed.json")["products"]
    members = load_json("members.seed.json")["members"]
    errors = check_seed_data(classes, products)
    if errors:
        sys.exit("Data seed tidak valid:\n  - " + "\n  - ".join(errors))

    if args.reset and DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()
        print(f"Database lama dihapus: {DEFAULT_DB_PATH.relative_to(ROOT)}")

    db = Database()
    db.init_schema()
    for product in products:
        db.upsert_product(product)
    for member in members:
        db.upsert_member(member["token"], now_wib())
    db.upsert_bin(DEMO_BIN["bin_id"], DEMO_BIN["location"], cfg["bin"]["capacity_g"])
    for member in members:
        if member.get("seed_at_daily_limit"):
            added = fill_daily_limit(db, member["token"], cfg, classes, products)
            print(f"{member['token']}: {added} setoran contoh (data demo) ditambahkan untuk hari ini")

    print(f"\nDatabase: {DEFAULT_DB_PATH.relative_to(ROOT)}")
    print(f"Produk  : {', '.join(f'{p} ({v['display']})' for p, v in db.get_products().items())}")
    limit = cfg["points"]["daily_limit_deposits"]
    for member in db.list_members():
        state = db.get_member_state(member["token"])
        print(f"Anggota : {member['token']}  poin={state['points_total']:>3}  "
              f"setoran hari ini={state['deposits_today']}/{limit}")
    b = db.get_bin(DEMO_BIN["bin_id"])
    print(f"Bin     : {b['bin_id']} ({b['location']})  isi {b['current_g']:.1f}/{b['capacity_g']:.0f} g "
          f"= {b['fill_pct']}%  status={b['status']}")


if __name__ == "__main__":
    main()
