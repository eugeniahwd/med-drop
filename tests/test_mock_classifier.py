"""MockClassifier memakai dataset buatan di folder sementara, bukan foto asli."""

import cv2
import numpy as np
import pytest

from backend.classifier import load_classifier
from backend.classifier.mock import MockClassifier

CLASSES = [
    {"class_id": "prod_a", "kind": "product", "product_id": "P-A", "display": "Produk A", "prohibited": False},
    {"class_id": "prod_b", "kind": "product", "product_id": "P-B", "display": "Produk B", "prohibited": False},
    {"class_id": "non_drug", "kind": "reject", "display": "Bukan obat", "prohibited": False},
    {"class_id": "aerosol_inhaler", "kind": "prohibited", "display": "Aerosol / inhaler", "prohibited": True},
]


def textured_image(seed: int) -> np.ndarray:
    """Gambar acak dengan detail halus, supaya respons terhadap blur mirip foto kemasan asli."""
    noise = np.random.default_rng(seed).integers(0, 256, (300, 400, 3), dtype=np.uint8)
    return cv2.GaussianBlur(noise, (0, 0), 0.5)


def write(path, image) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return path.read_bytes()


@pytest.fixture
def mock(tmp_path):
    test, degraded = tmp_path / "test", tmp_path / "test_degraded"
    original = textured_image(1)
    files = {
        "a": write(test / "prod_a" / "a1.png", original),
        "b": write(test / "prod_b" / "b1.png", textured_image(2)),
        "aerosol": write(test / "aerosol_inhaler" / "x1.png", textured_image(3)),
        "ood": write(test / "out_of_dataset" / "lain1.png", textured_image(4)),
        "orphan": write(degraded / "prod_a" / "tidak-ada__blur-ringan.png", textured_image(5)),
    }
    for name, sigma in [("blur-ringan", 0.8), ("blur-sedang", 2), ("blur-berat", 6)]:
        files[name] = write(degraded / "prod_a" / f"a1__{name}.png", cv2.GaussianBlur(original, (0, 0), sigma))
    for name, factor in [("gelap-ringan", 0.6), ("gelap-sedang", 0.3), ("gelap-berat", 0.12)]:
        files[name] = write(degraded / "prod_a" / f"a1__{name}.png", (original * factor).astype(np.uint8))
    return MockClassifier(CLASSES, test, degraded), files


def test_known_test_photo_gets_its_folder_class_with_pseudo_confidence(mock):
    clf, files = mock
    r = clf.predict(files["a"])
    assert r["class_id"] == "prod_a"
    assert 0.88 <= r["confidence"] <= 0.98
    assert r["class_id"] == max(r["probs"], key=r["probs"].get)
    assert sum(r["probs"].values()) == pytest.approx(1, abs=1e-3)


def test_prediction_is_deterministic(mock):
    clf, files = mock
    assert clf.predict(files["a"]) == clf.predict(files["a"])


@pytest.mark.parametrize("key, expected", [("b", "prod_b"), ("aerosol", "aerosol_inhaler"), ("ood", "non_drug")])
def test_folder_convention(mock, key, expected):
    clf, files = mock
    assert clf.predict(files[key])["class_id"] == expected


@pytest.mark.parametrize("kind", ["blur", "gelap"])
def test_confidence_drops_with_degradation_and_heavy_drops_below_floor(mock, kind):
    clf, files = mock
    conf = [clf.predict(files[k])["confidence"] for k in ("a", f"{kind}-ringan", f"{kind}-sedang", f"{kind}-berat")]
    assert conf == sorted(conf, reverse=True) and len(set(conf)) == 4
    assert conf[-1] < 0.5
    assert clf.predict(files[f"{kind}-ringan"])["class_id"] == "prod_a"


def test_unknown_photo_is_low_confidence_reject_class(mock):
    clf, _ = mock
    r = clf.predict(b"foto yang tidak ada di dataset")
    assert r["class_id"] == "non_drug"
    assert r["confidence"] < 0.5
    assert len(set(r["probs"].values())) == 1


def test_degraded_photo_without_original_is_treated_as_unknown(mock):
    clf, files = mock
    assert clf.predict(files["orphan"])["confidence"] < 0.5


def test_factory_selects_backend_from_config():
    clf = load_classifier({"classifier": {"backend": "mock"}}, CLASSES)
    assert isinstance(clf, MockClassifier) and clf.is_mock
    with pytest.raises(NotImplementedError):
        load_classifier({"classifier": {"backend": "keras"}}, CLASSES)
