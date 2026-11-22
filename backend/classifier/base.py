"""Antarmuka classifier foto. Semua backend (mock, keras) wajib mengikuti bentuk ini."""

from abc import ABC, abstractmethod


class Classifier(ABC):
    name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def predict(self, image_bytes: bytes) -> dict:
        """Klasifikasikan satu foto.

        Mengembalikan {"class_id": str, "confidence": float, "probs": {class_id: float}},
        dengan class_id = kelas berprobabilitas tertinggi dan confidence = probabilitasnya.
        """
