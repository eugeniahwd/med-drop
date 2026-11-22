"""Membagi foto di dataset/raw/<class_id>/ menjadi train/val/test.

Foto asli disimpan di dataset/raw/<class_id>/ sebagai sumber utama. Skrip ini
menyalinnya ke dataset/{train,val,test}/<class_id>/ secara acak tetapi
deterministik (seed tetap per kelas), sekitar 60/20/20. Kelas di
TEST_ONLY_CLASSES (out_of_dataset) hanya masuk ke test karena gunanya menguji
barang yang tidak pernah dilihat model.

Folder train/val/test dibuat ulang setiap kali skrip jalan, jadi jangan menaruh
foto langsung di sana. Tambahkan foto ke raw/ lalu jalankan ulang.
PERHATIAN: menjalankan ulang setelah model dilatih (M5) bisa mengubah isi test,
sehingga model harus dilatih dan dievaluasi ulang.

Skrip berhenti (fail-closed) bila menemukan:
  - foto kembar atau hampir kembar (mencegah test "bocor" ke train),
  - foto yang tidak bisa dibaca,
  - file di train/val/test yang tidak ada di raw/ (agar tidak ada foto yang terhapus).

    python scripts/split_dataset.py
"""

import itertools
import json
import random
import shutil
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"
RAW = DATASET / "raw"
SPLITS = ("train", "val", "test")
TEST_ONLY_CLASSES = {"out_of_dataset"}
SEED = "meddrop-v1"
VAL_FRAC = 0.2
TEST_FRAC = 0.2
# Hanya format yang bisa dibaca OpenCV dan TensorFlow (dipakai di M5).
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
IGNORED_FILES = {".gitkeep", "thumbs.db", "desktop.ini", ".ds_store"}
# Jarak dHash maksimum (dari 64 bit) yang dianggap foto kembar.
DUPLICATE_MAX_DISTANCE = 6


def dhash(gray):
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    return (small[:, 1:] > small[:, :-1]).flatten()


def split_counts(n):
    """Jumlah (train, val, test) untuk n foto. Minimal 1 foto di val dan test."""
    n_test = max(1, round(n * TEST_FRAC))
    n_val = max(1, round(n * VAL_FRAC))
    return n - n_val - n_test, n_val, n_test


def collect_raw():
    """Kembalikan {class_id: [Path, ...]} dan daftar masalah yang ditemukan."""
    classes, problems = {}, []
    for class_dir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        files = []
        for f in sorted(class_dir.iterdir()):
            if not f.is_file() or f.name.lower() in IGNORED_FILES:
                continue
            if f.suffix.lower() not in IMAGE_EXTS:
                problems.append(f"Format tidak didukung (ubah ke JPG/PNG): {f.relative_to(DATASET)}")
                continue
            files.append(f)
        classes[class_dir.name] = files
    return classes, problems


def find_problems(classes):
    problems, hashes = [], {}
    for files in classes.values():
        for f in files:
            gray = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                problems.append(f"Foto tidak bisa dibaca: {f.relative_to(DATASET)}")
            else:
                hashes[f] = dhash(gray)
    for a, b in itertools.combinations(hashes, 2):
        distance = int((hashes[a] != hashes[b]).sum())
        if distance <= DUPLICATE_MAX_DISTANCE:
            problems.append(f"Foto kembar (jarak {distance}), hapus salah satu: "
                            f"{a.relative_to(DATASET)} ~ {b.relative_to(DATASET)}")
    return problems


def find_orphans():
    """File di train/val/test yang tidak punya pasangan di raw/ (akan hilang bila dihapus)."""
    orphans = []
    for split in SPLITS:
        for f in (DATASET / split).rglob("*"):
            if f.is_file() and f.name.lower() not in IGNORED_FILES:
                if not (RAW / f.parent.name / f.name).exists():
                    orphans.append(str(f.relative_to(DATASET)))
    return orphans


def main():
    if not RAW.is_dir():
        sys.exit(f"Folder {RAW} tidak ada.")
    classes, problems = collect_raw()
    problems += find_problems(classes)
    orphans = find_orphans()
    if orphans:
        problems.append("File berikut ada di train/val/test tetapi tidak di raw/. "
                        "Pindahkan ke raw/<class_id>/ dulu:\n    " + "\n    ".join(orphans))
    if problems:
        print("Pembagian dibatalkan karena:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    for split in SPLITS:
        shutil.rmtree(DATASET / split, ignore_errors=True)
        (DATASET / split).mkdir()

    manifest = {"seed": SEED, "val_frac": VAL_FRAC, "test_frac": TEST_FRAC, "classes": {}}
    print(f"{'kelas':<18}{'train':>6}{'val':>6}{'test':>6}")
    for class_id, files in classes.items():
        if not files:
            print(f"{class_id:<18}  (belum ada foto, dilewati)")
            continue
        if class_id in TEST_ONLY_CLASSES:
            assignment = {"train": [], "val": [], "test": files}
        elif len(files) < 3:
            print(f"{class_id:<18}  (kurang dari 3 foto, dilewati)")
            continue
        else:
            shuffled = files[:]
            random.Random(f"{SEED}-{class_id}").shuffle(shuffled)
            n_train, n_val, _ = split_counts(len(shuffled))
            assignment = {
                "train": shuffled[:n_train],
                "val": shuffled[n_train:n_train + n_val],
                "test": shuffled[n_train + n_val:],
            }
        manifest["classes"][class_id] = {}
        for split, split_files in assignment.items():
            if split_files:
                target = DATASET / split / class_id
                target.mkdir(parents=True, exist_ok=True)
                for f in split_files:
                    shutil.copy2(f, target / f.name)
            manifest["classes"][class_id][split] = sorted(f.name for f in split_files)
        counts = [len(assignment[s]) for s in SPLITS]
        print(f"{class_id:<18}{counts[0]:>6}{counts[1]:>6}{counts[2]:>6}")

    (DATASET / "split.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDaftar pembagian disimpan di {(DATASET / 'split.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
