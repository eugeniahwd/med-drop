"""Mengisi database: produk, anggota fiktif, dan satu bin.

    python scripts/seed_db.py           # buat/lengkapi database; transaksi lama dipertahankan
    python scripts/seed_db.py --reset   # hapus database lalu buat ulang dari nol

MBR-0003 diberi setoran contoh hari ini sampai batas harian (data demo) agar
penolakan QUOTA bisa didemokan. Batas dihitung per hari (WIB), jadi jalankan
ulang skrip ini pada hari demo.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import load_classes, load_config  # noqa: E402
from backend.db import DEFAULT_DB_PATH, Database  # noqa: E402
from backend.seed import check_seed_data, load_seed_files, seed  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="hapus database lalu buat ulang dari nol")
    args = parser.parse_args()

    cfg, classes = load_config(), load_classes()
    products, members = load_seed_files()
    errors = check_seed_data(classes, products)
    if errors:
        sys.exit("Data seed tidak valid:\n  - " + "\n  - ".join(errors))

    if args.reset and DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()
        print(f"Database lama dihapus: {DEFAULT_DB_PATH.relative_to(ROOT)}")

    db = Database()
    for token, added in seed(db, cfg, classes, products, members).items():
        print(f"{token}: {added} setoran contoh (data demo) ditambahkan untuk hari ini")

    print(f"\nDatabase: {DEFAULT_DB_PATH.relative_to(ROOT)}")
    print(f"Produk  : {', '.join(f'{p} ({v['display']})' for p, v in db.get_products().items())}")
    limit = cfg["points"]["daily_limit_deposits"]
    for member in db.list_members():
        state = db.get_member_state(member["token"])
        print(f"Anggota : {member['token']}  poin={state['points_total']:>3}  "
              f"setoran hari ini={state['deposits_today']}/{limit}")
    for b in db.list_bins():
        print(f"Bin     : {b['bin_id']} ({b['location']})  isi {b['current_g']:.1f}/{b['capacity_g']:.0f} g "
              f"= {b['fill_pct']}%  status={b['status']}")


if __name__ == "__main__":
    main()
