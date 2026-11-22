"""MockClassifier: BUKAN model sungguhan.

Dipakai sementara sampai model asli (milestone M5) siap. Selama mock aktif,
UI menampilkan banner "MOCK CLASSIFIER AKTIF".

Cara kerja:
- Kelas ditentukan dari konvensi folder dataset, bukan dari isi gambar. Foto
  dikenali dari sidik jari isi file (SHA-256) yang cocok dengan file di
  dataset/test/<class_id>/ atau dataset/test_degraded/<class_id>/.
  Folder out_of_dataset dipetakan ke kelas 'reject' (non_drug).
- Keyakinan dasar bersifat semu: 0.88 sampai 0.98, tetap untuk tiap foto.
- Untuk foto buram/gelap (dataset/test_degraded/<class_id>/<nama_asli>__<varian>.jpg),
  keyakinan diturunkan sebanding dengan degradasi yang diukur dari pikselnya,
  dibandingkan dengan foto aslinya: hilangnya ketajaman diukur dalam dekade
  (kelipatan 10) dan hilangnya kecerahan dalam stop (kelipatan 2, seperti
  eksposur kamera).
- Foto yang tidak dikenal mendapat probabilitas rata di semua kelas, sehingga
  keyakinannya rendah dan ditolak sebagai tidak teridentifikasi.
"""

import hashlib
import math
from pathlib import Path

import cv2
import numpy as np

from backend.classifier.base import Classifier
from backend.config import ROOT_DIR

TEST_DIR = ROOT_DIR / "dataset" / "test"
DEGRADED_DIR = ROOT_DIR / "dataset" / "test_degraded"
OUT_OF_DATASET = "out_of_dataset"
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
BASE_CONF_MIN, BASE_CONF_SPAN = 0.88, 0.10
# Besar degradasi yang membuat keyakinan turun sampai nol (penurunan linear di antaranya).
SHARPNESS_DECADES_TO_ZERO = 4.0  # ketajaman tinggal 1/10.000 dari aslinya
BRIGHTNESS_STOPS_TO_ZERO = 5.0   # kecerahan tinggal 1/32 dari aslinya


class MockClassifier(Classifier):
    name = "mock"
    is_mock = True

    def __init__(self, classes: list, test_dir: Path = TEST_DIR, degraded_dir: Path = DEGRADED_DIR):
        self.class_ids = [c["class_id"] for c in classes]
        self.reject_class = next(c["class_id"] for c in classes if c["kind"] == "reject")
        self._index = {}  # sha256 -> {"class_id", "quality"}
        originals = {}    # (folder, stem) -> path
        for folder, class_id, path in self._scan(test_dir):
            originals[(folder, path.stem)] = path
            self._index[_sha256(path.read_bytes())] = {"class_id": class_id, "quality": 1.0}
        for folder, class_id, path in self._scan(degraded_dir):
            original = originals.get((folder, path.stem.split("__")[0]))
            if original is not None:  # tanpa foto asli, degradasi tidak bisa diukur: biarkan tak dikenal
                self._index[_sha256(path.read_bytes())] = {"class_id": class_id,
                                                           "quality": degradation_quality(path, original)}

    def _scan(self, root: Path):
        if not root.is_dir():
            return
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            class_id = self.reject_class if folder.name == OUT_OF_DATASET else folder.name
            if class_id not in self.class_ids:
                continue
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() in IMAGE_EXTS:
                    yield folder.name, class_id, path

    def predict(self, image_bytes: bytes) -> dict:
        digest = _sha256(image_bytes)
        entry = self._index.get(digest)
        if entry is None:
            uniform = round(1 / len(self.class_ids), 4)
            return {"class_id": self.reject_class, "confidence": uniform,
                    "probs": {c: uniform for c in self.class_ids}}

        seed = int(digest[:8], 16)
        base = BASE_CONF_MIN + (seed % 1000) / 1000 * BASE_CONF_SPAN
        probs = {entry["class_id"]: base * entry["quality"]}
        # Sisa probabilitas dibagi ke kelas lain dengan bobot 1/2, 1/3, 1/4, ... dalam urutan acak-tetap.
        others = [c for c in self.class_ids if c != entry["class_id"]]
        rotation = seed % len(others)
        others = others[rotation:] + others[:rotation]
        weights = [1 / (i + 2) for i in range(len(others))]
        rest = 1 - probs[entry["class_id"]]
        for class_id, w in zip(others, weights):
            probs[class_id] = rest * w / sum(weights)
        probs = {c: round(p, 4) for c, p in probs.items()}
        top = max(probs, key=probs.get)
        return {"class_id": top, "confidence": probs[top], "probs": probs}


def degradation_quality(image_path: Path, original_path: Path) -> float:
    """Kualitas 0..1 foto dibanding aslinya (1 = tidak terdegradasi)."""
    sharp, bright = _sharpness_brightness(image_path)
    sharp_ref, bright_ref = _sharpness_brightness(original_path)
    sharp_ratio = min(1.0, sharp / sharp_ref) if sharp_ref > 0 else 1.0
    bright_ratio = min(1.0, bright / bright_ref) if bright_ref > 0 else 1.0
    sharp_loss_decades = -math.log10(max(sharp_ratio, 1e-12))
    bright_loss_stops = -math.log2(max(bright_ratio, 1e-12))
    sharp_quality = max(0.0, 1 - sharp_loss_decades / SHARPNESS_DECADES_TO_ZERO)
    bright_quality = max(0.0, 1 - bright_loss_stops / BRIGHTNESS_STOPS_TO_ZERO)
    return sharp_quality * bright_quality


def _sharpness_brightness(path: Path) -> tuple[float, float]:
    """Ketajaman (varians Laplacian dinormalisasi kecerahan) dan kecerahan rata-rata."""
    gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    scale = 256 / max(gray.shape)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA).astype(np.float64)
    mean = gray.mean()
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var() / (mean ** 2) if mean > 0 else 0.0
    return sharpness, mean


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
