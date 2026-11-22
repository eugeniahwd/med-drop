"""Pemilihan backend classifier berdasarkan config.yaml (classifier.backend)."""

from backend.classifier.base import Classifier


def load_classifier(config: dict, classes: list) -> Classifier:
    backend = config["classifier"]["backend"]
    if backend == "mock":
        from backend.classifier.mock import MockClassifier
        return MockClassifier(classes)
    if backend == "keras":
        raise NotImplementedError("Backend 'keras' belum tersedia; model asli dibuat di milestone M5.")
    raise ValueError(f"Backend classifier tidak dikenal: {backend!r}")
