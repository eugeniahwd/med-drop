"""Classifier asli: MobileNetV2 hasil transfer learning (dilatih dengan scripts/train.py)."""

import json

import cv2
import numpy as np

from backend.classifier.base import Classifier
from backend.config import ROOT_DIR

MODEL_DIR = ROOT_DIR / "model"
IMAGE_SIZE = 224


class KerasClassifier(Classifier):
    name = "keras"
    is_mock = False

    def __init__(self, model_dir=MODEL_DIR):
        import tensorflow as tf  # diimpor di sini supaya backend mock tidak butuh TensorFlow

        self.model = tf.keras.models.load_model(model_dir / "model.keras")
        self.labels = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))

    def predict(self, image_bytes):
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        image = cv2.cvtColor(cv2.resize(image, (IMAGE_SIZE, IMAGE_SIZE)), cv2.COLOR_BGR2RGB)
        scores = self.model.predict(image[None].astype("float32"), verbose=0)[0]
        probs = {label: round(float(p), 4) for label, p in zip(self.labels, scores)}
        top = max(probs, key=probs.get)
        return {"class_id": top, "confidence": probs[top], "probs": probs}
