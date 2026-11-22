"""MockClassifier: BUKAN model sungguhan, hanya pengganti sampai model asli (M5) siap.

Foto dikenali dari isi file (hash) yang sama persis dengan foto di
dataset/test/<kelas>/ atau dataset/test_degraded/<kelas>/, lalu diberi
keyakinan buatan. Foto buram/gelap keyakinannya dikurangi sesuai tingkatnya,
yang dibaca dari nama file (misalnya promag-1__gelap-berat.jpg).
Foto lain yang tidak dikenal dianggap tidak teridentifikasi.
"""

import hashlib

from backend.classifier.base import Classifier
from backend.config import ROOT_DIR

DATASET_DIR = ROOT_DIR / "dataset"
DEGRADE_FACTOR = {"ringan": 0.88, "sedang": 0.65, "berat": 0.4}


class MockClassifier(Classifier):
    name = "mock"
    is_mock = True

    def __init__(self, classes, dataset_dir=DATASET_DIR):
        self.class_ids = [c["class_id"] for c in classes]
        self.reject_class = next(c["class_id"] for c in classes if c["kind"] == "reject")
        self.known = {}  # hash -> (class_id, pengali keyakinan)
        for split in ("test", "test_degraded"):
            for path in sorted((dataset_dir / split).glob("*/*")):
                if path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    continue
                class_id = path.parent.name
                if class_id == "out_of_dataset":
                    class_id = self.reject_class
                if class_id not in self.class_ids:
                    continue
                level = path.stem.split("-")[-1] if "__" in path.stem else None
                factor = DEGRADE_FACTOR.get(level, 1.0)
                self.known[hashlib.sha256(path.read_bytes()).hexdigest()] = (class_id, factor)

    def predict(self, image_bytes):
        digest = hashlib.sha256(image_bytes).hexdigest()
        if digest not in self.known:
            p = round(1 / len(self.class_ids), 4)
            return {"class_id": self.reject_class, "confidence": p, "probs": {c: p for c in self.class_ids}}

        class_id, factor = self.known[digest]
        base = 0.88 + int(digest[:4], 16) % 100 / 1000  # 0.88 sampai 0.979, tetap untuk tiap foto
        confidence = round(base * factor, 4)
        rest = round((1 - confidence) / (len(self.class_ids) - 1), 4)
        probs = {c: rest for c in self.class_ids}
        probs[class_id] = confidence
        top = max(probs, key=probs.get)
        return {"class_id": top, "confidence": probs[top], "probs": probs}
