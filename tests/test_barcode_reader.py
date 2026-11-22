import cv2
import numpy as np
import pytest

from backend import ean13
from backend.barcode_reader import read_barcode
from backend.config import ROOT_DIR

BARCODE_DIR = ROOT_DIR / "data" / "barcodes"


def png_bytes(image) -> bytes:
    return cv2.imencode(".png", image)[1].tobytes()


def clean_barcode(code: str, module_px: int = 3) -> np.ndarray:
    """Barcode digital yang sangat bersih dengan margin sempit."""
    row = np.array([0 if bit == "1" else 255 for bit in ean13.bar_pattern(code)], np.uint8)
    image = np.repeat(np.repeat(row[None, :], 100, 0), module_px, 1)
    return cv2.copyMakeBorder(image, 10, 10, 30, 30, cv2.BORDER_CONSTANT, value=255)


@pytest.mark.parametrize("path", sorted(BARCODE_DIR.glob("*.png")), ids=lambda p: p.stem)
def test_generated_barcode_images_are_decoded(path):
    assert read_barcode(path.read_bytes()) == {
        "present": True, "decoded": path.stem, "symbology": "EAN_13", "source": "image"}


def test_clean_digital_barcode_is_decoded():
    assert read_barcode(png_bytes(clean_barcode("2000000000022")))["decoded"] == "2000000000022"


@pytest.mark.parametrize("image, text", [(None, None), (b"", ""), (None, "   ")])
def test_nothing_given_means_no_barcode(image, text):
    assert read_barcode(image, text)["present"] is False


def test_text_only_is_used_as_is():
    r = read_barcode(text=" 2000000000015 ")
    assert (r["present"], r["decoded"], r["symbology"]) == (True, "2000000000015", "TEXT")


def test_blank_image_is_present_but_unreadable():
    r = read_barcode(png_bytes(np.full((200, 300), 255, np.uint8)))
    assert (r["present"], r["decoded"]) == (True, None)


def test_non_image_bytes_are_unreadable():
    r = read_barcode(b"ini bukan gambar")
    assert (r["present"], r["decoded"]) == (True, None)


def test_image_and_text_that_disagree_fail_closed():
    image = (BARCODE_DIR / "2000000000015.png").read_bytes()
    r = read_barcode(image, text="2000000000022")
    assert (r["present"], r["decoded"]) == (True, None)


def test_image_and_text_that_agree_are_accepted():
    image = (BARCODE_DIR / "2000000000015.png").read_bytes()
    assert read_barcode(image, text="2000000000015")["decoded"] == "2000000000015"
