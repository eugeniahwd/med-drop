"""Buat PNG barcode EAN-13 dummy untuk setiap produk, plus satu kode yang tidak terdaftar.

Kode dummy berawalan 2 (dicadangkan GS1 untuk penggunaan internal), jadi tidak
bentrok dengan kode produk asli. Setiap PNG langsung dibaca ulang dengan OpenCV.

    python scripts/make_barcode_images.py
"""

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "barcodes"
UNREGISTERED = "2000000000992"  # untuk skenario barcode tidak terdaftar

# Pola EAN-13 (1 = batang hitam)
L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]
PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def check_digit(first12):
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def bars(code):
    assert len(code) == 13 and check_digit(code[:12]) == code[12], f"EAN-13 tidak valid: {code}"
    left = "".join((L if p == "L" else G)[int(d)] for p, d in zip(PARITY[int(code[0])], code[1:7]))
    right = "".join(R[int(d)] for d in code[7:])
    return "101" + left + "01010" + right + "101"


def render(code, module=3, height=150):
    pattern = bars(code)
    quiet = 12 * module
    img = np.full((height + 30, quiet * 2 + len(pattern) * module), 255, np.uint8)
    for i, bit in enumerate(pattern):
        if bit == "1":
            long_bar = i < 3 or 45 <= i < 50 or i >= 92  # batang pembatas lebih panjang
            img[: height + (15 if long_bar else 0), quiet + i * module: quiet + (i + 1) * module] = 0
    for i, digit in enumerate(code):
        x = quiet + module * (-8 if i == 0 else 4 + 7 * (i - 1) if i < 7 else 51 + 7 * (i - 7))
        cv2.putText(img, digit, (x, height + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1, cv2.LINE_AA)
    # margin dan sedikit blur supaya mirip foto kamera (detektor OpenCV lebih mudah membacanya)
    img = cv2.copyMakeBorder(img, 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=255)
    return cv2.GaussianBlur(img, (3, 3), 0)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    products = json.loads((ROOT / "data" / "products.seed.json").read_text(encoding="utf-8"))["products"]
    detector = cv2.barcode.BarcodeDetector()
    for code in [p["barcode"] for p in products] + [UNREGISTERED]:
        path = OUT_DIR / f"{code}.png"
        cv2.imwrite(str(path), render(code))
        ok, infos, _, _ = detector.detectAndDecodeWithType(cv2.imread(str(path)))
        print(path.relative_to(ROOT), "OK" if ok and infos[0] == code else "GAGAL DIBACA")


if __name__ == "__main__":
    main()
