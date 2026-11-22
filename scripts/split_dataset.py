"""Bagi foto di dataset/raw/<kelas>/ ke train/val/test (sekitar 60/20/20, acak tapi tetap).

Foto asli ada di raw/. Folder train/val/test dibuat ulang setiap kali skrip
jalan, jadi tambahkan foto baru ke raw/ lalu jalankan ulang. Kelas
out_of_dataset hanya masuk test karena dipakai untuk menguji obat yang tidak dikenal.

    python scripts/split_dataset.py
"""

import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"
RAW = DATASET / "raw"
SPLITS = ("train", "val", "test")
SEED = "meddrop-v1"


def main():
    # Jangan sampai foto yang ditaruh langsung di train/val/test ikut terhapus.
    for split in SPLITS:
        for f in (DATASET / split).rglob("*.*"):
            if not (RAW / f.parent.name / f.name).exists():
                sys.exit(f"{f.relative_to(DATASET)} tidak ada di raw/. Pindahkan dulu ke raw/{f.parent.name}/")
        shutil.rmtree(DATASET / split, ignore_errors=True)

    manifest = {}
    for class_dir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        photos = sorted(p for p in class_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        if not photos:
            continue
        random.Random(f"{SEED}-{class_dir.name}").shuffle(photos)
        if class_dir.name == "out_of_dataset":
            parts = {"train": [], "val": [], "test": photos}
        else:
            n_test = n_val = max(1, round(len(photos) * 0.2))
            parts = {"test": photos[:n_test], "val": photos[n_test:n_test + n_val], "train": photos[n_test + n_val:]}
        for split, files in parts.items():
            for f in files:
                (DATASET / split / class_dir.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, DATASET / split / class_dir.name / f.name)
        manifest[class_dir.name] = {s: sorted(f.name for f in parts[s]) for s in SPLITS}
        print(f"{class_dir.name:<16} train {len(parts['train']):>2}  val {len(parts['val']):>2}  test {len(parts['test']):>2}")

    (DATASET / "split.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
