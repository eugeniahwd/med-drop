"""Kartu item uji untuk demo web (data/items.json).

`ground_truth`, `expected_decision`, dan `expected_reason` hanya untuk label
skenario dan evaluasi di UI. Engine keputusan tidak pernah menerimanya:
/api/verify hanya menerima foto, barcode, berat, dan identitas anggota/bin.
"""

import json
from pathlib import Path

from backend.config import ROOT_DIR, ConfigError

ITEMS_PATH = ROOT_DIR / "data" / "items.json"
BARCODE_DIR = ROOT_DIR / "data" / "barcodes"
# Foto kartu wajib dari split test (tidak pernah dipakai melatih model).
PHOTO_DIRS = {
    "/media/test": ROOT_DIR / "dataset" / "test",
    "/media/test_degraded": ROOT_DIR / "dataset" / "test_degraded",
}


def load_items(path: Path = ITEMS_PATH) -> list[dict]:
    """Baca dan validasi kartu item, lalu tambahkan URL foto dan gambar barcode."""
    if not path.exists():
        return []
    items, seen = [], set()
    for item in json.loads(path.read_text(encoding="utf-8")):
        item_id = item["item_id"]
        if item_id in seen:
            raise ConfigError(f"item_id ganda di items.json: {item_id}")
        seen.add(item_id)
        if item["expected_decision"] not in ("ACCEPT", "REJECT"):
            raise ConfigError(f"Kartu {item_id}: expected_decision harus ACCEPT atau REJECT")
        barcode = item.get("barcode")
        if barcode and not (BARCODE_DIR / f"{barcode}.png").is_file():
            raise ConfigError(f"Kartu {item_id}: gambar barcode {barcode} belum ada. "
                              "Jalankan scripts/make_barcode_images.py")
        items.append({
            **item,
            "photo_url": _photo_url(item_id, item["photo"]),
            "barcode_image_url": f"/media/barcodes/{barcode}.png" if barcode else None,
        })
    return items


def _photo_url(item_id: str, photo: str) -> str:
    path = (ROOT_DIR / photo).resolve()
    for url_prefix, directory in PHOTO_DIRS.items():
        if path.is_relative_to(directory.resolve()):
            if not path.is_file():
                raise ConfigError(f"Kartu {item_id}: foto tidak ditemukan: {photo}")
            return url_prefix + "/" + path.relative_to(directory.resolve()).as_posix()
    raise ConfigError(f"Kartu {item_id}: foto wajib dari dataset/test atau dataset/test_degraded, bukan {photo}")
