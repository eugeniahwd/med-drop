"""Membaca barcode kemasan dari gambar (OpenCV) atau dari teks.

Di mesin sungguhan, pemindai 2D imager biasanya langsung mengirim teks hasil
pindaian (`barcode_text`). Di simulasi, frontend mengirim gambar barcode
(`barcode_image`) supaya proses decode OpenCV benar-benar dijalankan.

Hasil:
    {"present": bool, "decoded": str | None, "symbology": str | None, "source": ...}
`present` berarti ada barcode yang disodorkan. `decoded` None berarti barcode
ada tetapi tidak terbaca, dan engine keputusan akan menolaknya (fail-closed).
"""

import cv2
import numpy as np

PAD_PX = 60


def read_barcode(image_bytes: bytes | None = None, text: str | None = None) -> dict:
    text = (text or "").strip() or None
    if not image_bytes and text is None:
        return {"present": False, "decoded": None, "symbology": None, "source": None}
    if not image_bytes:
        return {"present": True, "decoded": text, "symbology": "TEXT", "source": "text"}

    decoded, symbology = decode_image(image_bytes)
    if text is not None and decoded != text:
        # Gambar dan teks tidak sepakat: anggap tidak terbaca (fail-closed).
        return {"present": True, "decoded": None, "symbology": None, "source": "image+text"}
    return {"present": True, "decoded": decoded, "symbology": symbology, "source": "image"}


def decode_image(image_bytes: bytes) -> tuple[str | None, str | None]:
    """Kembalikan (isi, jenis) barcode pertama yang terbaca, atau (None, None)."""
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None, None
    detector = cv2.barcode.BarcodeDetector()
    for candidate in _candidates(image):
        ok, infos, types, _ = detector.detectAndDecodeWithType(candidate)
        if ok:
            for info, kind in zip(infos, types):
                if info:
                    return info, kind
    return None, None


def _candidates(image):
    """Gambar asli, lalu varian yang membantu detektor pada gambar digital yang terlalu bersih."""
    yield image
    padded = cv2.copyMakeBorder(image, PAD_PX, PAD_PX, PAD_PX, PAD_PX,
                                cv2.BORDER_CONSTANT, value=(255, 255, 255))
    yield cv2.GaussianBlur(padded, (3, 3), 0)
    yield cv2.resize(padded, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
