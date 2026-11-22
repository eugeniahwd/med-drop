"""Membuat PNG barcode EAN-13 dummy.

Kode diambil dari data/products.seed.json, data/items.json (bila sudah ada),
dan EXTRA_CODES (kode valid tetapi tidak terdaftar, untuk skenario
BARCODE_INVALID). Gambar dibuat mirip hasil kamera, dengan margin putih lebar
dan sedikit blur, lalu langsung dibaca ulang dengan OpenCV sebagai pemeriksaan.
Barcode ini dummy (awalan 2), bukan GTIN produk asli.

    python scripts/make_barcode_images.py
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import ean13  # noqa: E402

DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "barcodes"
EXTRA_CODES = ["2000000000992"]  # EAN-13 valid, sengaja tidak terdaftar sebagai produk

MODULE_PX = 3           # lebar satu modul (batang tersempit)
BAR_HEIGHT_PX = 150
GUARD_EXTRA_PX = 15     # batang pembatas sedikit lebih panjang, seperti barcode asli
TEXT_AREA_PX = 30
QUIET_ZONE_MODULES = 12
MARGIN_PX = 60          # ruang kosong di sekitar barcode, seperti foto kemasan
GUARD_MODULES = set(range(0, 3)) | set(range(45, 50)) | set(range(92, 95))


def collect_codes() -> list[str]:
    products = json.loads((DATA_DIR / "products.seed.json").read_text(encoding="utf-8"))["products"]
    codes = [p["barcode"] for p in products]
    items_path = DATA_DIR / "items.json"
    if items_path.exists():
        codes += [i["barcode"] for i in json.loads(items_path.read_text(encoding="utf-8")) if i.get("barcode")]
    codes += EXTRA_CODES
    return list(dict.fromkeys(codes))  # hapus duplikat, urutan tetap


def render_barcode(code: str) -> np.ndarray:
    bits = ean13.bar_pattern(code)
    quiet = QUIET_ZONE_MODULES * MODULE_PX
    width = quiet * 2 + len(bits) * MODULE_PX
    image = np.full((BAR_HEIGHT_PX + TEXT_AREA_PX, width), 255, np.uint8)
    for i, bit in enumerate(bits):
        if bit == "1":
            x = quiet + i * MODULE_PX
            height = BAR_HEIGHT_PX + (GUARD_EXTRA_PX if i in GUARD_MODULES else 0)
            image[:height, x:x + MODULE_PX] = 0

    # Angka di bawah batang: digit pertama di kiri, lalu 6 digit kiri dan 6 digit kanan.
    def put_digit(digit, module_x):
        cv2.putText(image, digit, (quiet + module_x * MODULE_PX, BAR_HEIGHT_PX + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1, cv2.LINE_AA)
    put_digit(code[0], -8)
    for k, digit in enumerate(code[1:7]):
        put_digit(digit, 4 + 7 * k)
    for k, digit in enumerate(code[7:]):
        put_digit(digit, 51 + 7 * k)

    image = cv2.copyMakeBorder(image, *[MARGIN_PX] * 4, cv2.BORDER_CONSTANT, value=255)
    return cv2.GaussianBlur(image, (3, 3), 0)


def decode(path: Path) -> tuple[str, str]:
    ok, infos, types, _ = cv2.barcode.BarcodeDetector().detectAndDecodeWithType(cv2.imread(str(path)))
    return (infos[0], types[0]) if ok and infos else ("", "")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for code in collect_codes():
        if not ean13.is_dummy(code):
            failed.append(code)
            print(f"{code}  [DILEWATI: bukan EAN-13 dummy valid berawalan 2]")
            continue
        path = OUT_DIR / f"{code}.png"
        cv2.imwrite(str(path), render_barcode(code))
        decoded, symbology = decode(path)
        ok = decoded == code and symbology == "EAN_13"
        if not ok:
            failed.append(code)
        print(f"{path.relative_to(ROOT)}  [{'OK' if ok else f'GAGAL (terbaca {decoded!r} {symbology})'}]")
    if failed:
        sys.exit(f"{len(failed)} barcode bermasalah.")


if __name__ == "__main__":
    main()
