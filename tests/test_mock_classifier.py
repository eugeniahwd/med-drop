import cv2
import numpy as np
import pytest

from backend.classifier import load_classifier
from backend.classifier.mock import MockClassifier

CLASSES = [
    {"class_id": "prod_a", "kind": "product", "product_id": "P-A", "display": "Produk A", "prohibited": False},
    {"class_id": "non_drug", "kind": "reject", "display": "Bukan obat", "prohibited": False},
    {"class_id": "aerosol_inhaler", "kind": "prohibited", "display": "Aerosol / inhaler", "prohibited": True},
]


def save(path, seed):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.random.default_rng(seed).integers(0, 256, (60, 80, 3), dtype=np.uint8))
    return path.read_bytes()


@pytest.fixture
def mock(tmp_path):
    files = {
        "a": save(tmp_path / "test/prod_a/a1.png", 1),
        "aerosol": save(tmp_path / "test/aerosol_inhaler/x1.png", 2),
        "ood": save(tmp_path / "test/out_of_dataset/lain1.png", 3),
        "ringan": save(tmp_path / "test_degraded/prod_a/a1__blur-ringan.png", 4),
        "berat": save(tmp_path / "test_degraded/prod_a/a1__gelap-berat.png", 5),
    }
    return MockClassifier(CLASSES, tmp_path), files


def test_known_photo_gets_class_from_folder(mock):
    clf, files = mock
    r = clf.predict(files["a"])
    assert r["class_id"] == "prod_a" and 0.88 <= r["confidence"] < 0.98
    assert clf.predict(files["aerosol"])["class_id"] == "aerosol_inhaler"
    assert clf.predict(files["ood"])["class_id"] == "non_drug"


def test_degraded_photos_get_lower_confidence(mock):
    clf, files = mock
    a, ringan, berat = (clf.predict(files[k])["confidence"] for k in ("a", "ringan", "berat"))
    assert a > ringan > berat
    assert berat < 0.5


def test_unknown_photo_is_not_recognized(mock):
    clf, _ = mock
    r = clf.predict(b"foto lain")
    assert r["class_id"] == "non_drug" and r["confidence"] < 0.5


def test_factory_picks_mock_from_config():
    assert load_classifier({"classifier": {"backend": "mock"}}, CLASSES).is_mock
