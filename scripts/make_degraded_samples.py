"""Membuat varian buram dan gelap dari sebagian foto test.

Untuk setiap kelas produk, foto test pertama (urut nama) dibuat menjadi
3 tingkat buram dan 3 tingkat gelap:
    dataset/test_degraded/<class_id>/<nama_asli>__blur-ringan.jpg, ...
Varian ini tetap bagian dari split test (tidak pernah dipakai melatih model)
dan dipakai untuk skenario "foto buram/gelap" serta evaluasi.

Folder test_degraded dibuat ulang setiap kali skrip jalan. Jalankan ulang
setelah scripts/split_dataset.py, karena isi test bisa berubah.

    python scripts/make_degraded_samples.py
"""

import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "dataset" / "test"
OUT_DIR = ROOT / "dataset" / "test_degraded"
CLASSES_PATH = ROOT / "data" / "classes.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# Sigma Gaussian blur, relatif terhadap foto selebar 800 px.
BLUR_LEVELS = {"ringan": 1.5, "sedang": 4.0, "berat": 10.0}
# Faktor pengali kecerahan.
DARK_LEVELS = {"ringan": 0.6, "sedang": 0.3, "berat": 0.12}


def blur(image: np.ndarray, sigma_at_800: float) -> np.ndarray:
    sigma = sigma_at_800 * image.shape[1] / 800
    return cv2.GaussianBlur(image, (0, 0), sigma)


def darken(image: np.ndarray, factor: float) -> np.ndarray:
    return np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def main():
    product_classes = [c["class_id"] for c in json.loads(CLASSES_PATH.read_text(encoding="utf-8"))
                       if c["kind"] == "product"]
    if OUT_DIR.exists():
        unexpected = [p for p in OUT_DIR.rglob("*") if p.is_file() and "__" not in p.name]
        if unexpected:
            sys.exit("Dibatalkan: ada file di test_degraded yang bukan buatan skrip ini:\n  "
                     + "\n  ".join(str(p.relative_to(ROOT)) for p in unexpected))
        shutil.rmtree(OUT_DIR)

    for class_id in product_classes:
        sources = sorted(p for p in (TEST_DIR / class_id).glob("*") if p.suffix.lower() in IMAGE_EXTS)
        if not sources:
            print(f"{class_id}: tidak ada foto test, dilewati")
            continue
        source = sources[0]
        image = cv2.imread(str(source))
        target = OUT_DIR / class_id
        target.mkdir(parents=True, exist_ok=True)
        for level, sigma in BLUR_LEVELS.items():
            cv2.imwrite(str(target / f"{source.stem}__blur-{level}.jpg"), blur(image, sigma))
        for level, factor in DARK_LEVELS.items():
            cv2.imwrite(str(target / f"{source.stem}__gelap-{level}.jpg"), darken(image, factor))
        print(f"{class_id}: 6 varian dari {source.name}")


if __name__ == "__main__":
    main()
