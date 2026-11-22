import cv2
import numpy as np
import pytest

from backend.barcode_reader import read_barcode
from backend.config import ROOT_DIR

BARCODE_DIR = ROOT_DIR / "data" / "barcodes"


@pytest.mark.parametrize("path", sorted(BARCODE_DIR.glob("*.png")), ids=lambda p: p.stem)
def test_barcode_images_are_decoded(path):
    assert read_barcode(path.read_bytes()) == {"present": True, "decoded": path.stem, "symbology": "EAN_13"}


def test_text_from_scanner():
    assert read_barcode(text=" 2000000000015 ") == {"present": True, "decoded": "2000000000015", "symbology": "TEXT"}


def test_no_barcode():
    assert read_barcode(None, "")["present"] is False


def test_image_without_barcode_is_unreadable():
    blank = cv2.imencode(".png", np.full((200, 300), 255, np.uint8))[1].tobytes()
    assert read_barcode(blank) == {"present": True, "decoded": None, "symbology": None}
    assert read_barcode(b"bukan gambar")["decoded"] is None
