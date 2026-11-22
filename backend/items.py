"""Kartu item uji untuk demo web (data/items.json).

ground_truth dan expected_* hanya untuk label skenario di UI. Engine keputusan
tidak pernah menerimanya: /api/verify hanya menerima foto, barcode, dan berat.
"""

import json

from backend.config import ROOT_DIR

ITEMS_PATH = ROOT_DIR / "data" / "items.json"


def load_items(path=ITEMS_PATH):
    if not path.exists():
        return []
    items = json.loads(path.read_text(encoding="utf-8"))
    for item in items:
        photo = item["photo"]
        # Foto kartu wajib dari split test, yang tidak pernah dipakai melatih model.
        if not photo.startswith(("dataset/test/", "dataset/test_degraded/")):
            raise ValueError(f"{item['item_id']}: foto kartu harus dari dataset/test, bukan {photo}")
        item["photo_url"] = "/media/" + photo.removeprefix("dataset/")
        item["barcode_image_url"] = f"/media/barcodes/{item['barcode']}.png" if item.get("barcode") else None
    return items
