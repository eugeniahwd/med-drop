"""Isi database: produk, anggota fiktif, dan satu bin.

    python scripts/seed_db.py           # buat/lengkapi database, transaksi lama tetap ada
    python scripts/seed_db.py --reset   # hapus database lalu buat ulang

Batas setoran dihitung per hari (WIB), jadi jalankan ulang di hari demo agar
MBR-0003 sudah mencapai batas hariannya.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import load_classes, load_config  # noqa: E402
from backend.db import DEFAULT_DB_PATH, Database  # noqa: E402
from backend.seed import load_seed_files, seed  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="hapus database lalu buat ulang")
    args = parser.parse_args()

    if args.reset and DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()

    cfg = load_config()
    db = Database()
    products, members = load_seed_files()
    for token, added in seed(db, cfg, load_classes(), products, members).items():
        print(f"{token}: {added} setoran contoh ditambahkan untuk hari ini")

    limit = cfg["points"]["daily_limit_deposits"]
    for member in db.list_members():
        state = db.get_member_state(member["token"])
        print(f"{member['token']}  poin={state['points_total']:>3}  setoran hari ini={state['deposits_today']}/{limit}")
    for b in db.list_bins():
        print(f"{b['bin_id']}  isi {b['current_g']:.1f}/{b['capacity_g']:.0f} g ({b['fill_pct']}%)")


if __name__ == "__main__":
    main()
