"""Ubah beberapa foto uji menjadi array C untuk firmware ESP32 (firmware/include/photos.h).

ESP32 Dev Module tidak punya kamera, jadi foto disimpan di memori firmware sebagai
pengganti kamera. Foto diperkecil ke 320 px supaya muat dan cepat dikirim.

    python scripts/make_firmware_photos.py
"""

from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = [  # dari split test, jadi belum pernah dilihat model saat latihan
    "dataset/test/entrostop/entrostop-9.jpg",
    "dataset/test/promag/promag-4.jpg",
    "dataset/test/non_drug/botol-02.jpg",
]
MAX_SIDE = 320


def main():
    lines = ["// Dibuat oleh scripts/make_firmware_photos.py, jangan diedit manual.", "#pragma once",
             "#include <Arduino.h>", "", "struct Photo { const char *name; const uint8_t *data; size_t size; };", ""]
    entries = []
    for i, rel in enumerate(PHOTOS):
        img = cv2.imread(str(ROOT / rel))
        scale = MAX_SIDE / max(img.shape[:2])
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
        (ROOT / "firmware" / "include").mkdir(parents=True, exist_ok=True)
        hex_lines = [", ".join(f"0x{b:02x}" for b in data[j:j + 16]) for j in range(0, len(data), 16)]
        lines += [f"const uint8_t PHOTO_{i}[] = {{", *[f"  {h}," for h in hex_lines], "};", ""]
        entries.append(f'  {{"{Path(rel).name}", PHOTO_{i}, sizeof(PHOTO_{i})}},')
        print(f"{rel} -> {len(data) / 1024:.1f} KB")
    lines += ["const Photo PHOTOS[] = {", *entries, "};", f"const int PHOTO_COUNT = {len(PHOTOS)};", ""]
    (ROOT / "firmware" / "include" / "photos.h").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
