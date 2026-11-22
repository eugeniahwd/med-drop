"""Pilih backend classifier dari config.yaml (classifier.backend: mock | keras)."""

from backend.classifier.base import Classifier


def load_classifier(config, classes) -> Classifier:
    if config["classifier"]["backend"] == "keras":
        from backend.classifier.keras_model import KerasClassifier
        return KerasClassifier()
    from backend.classifier.mock import MockClassifier
    return MockClassifier(classes)
