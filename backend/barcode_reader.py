"""Baca barcode kemasan dari gambar (OpenCV) atau dari teks hasil pemindai.

Di simulasi, frontend mengirim gambar barcode supaya decode OpenCV benar-benar jalan.
Mesin asli bisa langsung mengirim teks dari modul pemindai (barcode_text).
"""

import cv2
import numpy as np


def read_barcode(image_bytes=None, text=None):
    """Hasil: {"present", "decoded", "symbology"}. decoded None berarti ada barcode tapi tidak terbaca."""
    text = (text or "").strip()
    if image_bytes:
        decoded, symbology = decode_image(image_bytes)
        return {"present": True, "decoded": decoded, "symbology": symbology}
    if text:
        return {"present": True, "decoded": text, "symbology": "TEXT"}
    return {"present": False, "decoded": None, "symbology": None}


def decode_image(image_bytes):
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None, None
    detector = cv2.barcode.BarcodeDetector()
    # Detektor OpenCV kadang gagal pada gambar digital yang terlalu bersih,
    # jadi dicoba juga versi yang diberi margin putih dan sedikit blur.
    padded = cv2.copyMakeBorder(image, 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    for candidate in (image, cv2.GaussianBlur(padded, (3, 3), 0)):
        ok, infos, types, _ = detector.detectAndDecodeWithType(candidate)
        if ok and infos and infos[0]:
            return infos[0], types[0]
    return None, None
