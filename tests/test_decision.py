"""Tabel kasus engine keputusan: setiap reason_code, urutan aturan, dan batas threshold/berat.

Data uji dibuat di sini (bukan dibaca dari data/) agar tes tidak berubah saat data dummy diubah.
"""

import pytest

from backend.decision import REASON_TEXTS, decide

CONFIG = {
    "classifier": {"threshold_with_barcode": 0.60, "threshold_photo_only": 0.85, "min_confidence_floor": 0.50},
    "weight": {"empty_margin_g": 0.5, "empty_margin_pct": 3, "gross_tolerance_pct": 5},
    "points": {"per_valid_deposit": 10, "daily_limit_deposits": 3},
}
CLASSES = [
    {"class_id": "prod_a", "kind": "product", "product_id": "P-A", "display": "Produk A", "prohibited": False},
    {"class_id": "prod_b", "kind": "product", "product_id": "P-B", "display": "Produk B", "prohibited": False},
    {"class_id": "non_drug", "kind": "reject", "display": "Bukan obat", "prohibited": False},
    {"class_id": "aerosol_inhaler", "kind": "prohibited", "display": "Aerosol / inhaler", "prohibited": True},
]
PRODUCTS = {
    "P-A": {"product_id": "P-A", "display": "Produk A", "barcode": "2000000000015", "tare_g": 10, "gross_g": 50},
    "P-B": {"product_id": "P-B", "display": "Produk B", "barcode": "2000000000022", "tare_g": 4, "gross_g": 14},
}
BARCODE_A = {"present": True, "decoded": "2000000000015", "symbology": "EAN_13"}
BARCODE_B = {"present": True, "decoded": "2000000000022", "symbology": "EAN_13"}
BARCODE_UNKNOWN = {"present": True, "decoded": "2000000000992", "symbology": "EAN_13"}
BARCODE_UNREADABLE = {"present": True, "decoded": None, "symbology": None}
NO_BARCODE = {"present": False, "decoded": None, "symbology": None}


def photo(class_id, confidence):
    return {"class_id": class_id, "confidence": confidence, "probs": {class_id: confidence}}


def run(deposits_today=0, pred=None, barcode=BARCODE_A, weight_g=40.0):
    return decide({"deposits_today": deposits_today}, pred or photo("prod_a", 0.93), barcode, weight_g,
                  CONFIG, PRODUCTS, CLASSES)


# (nama kasus, argumen run, keputusan, reason_code)
CASES = [
    # --- setiap reason_code ---
    ("terima dengan barcode", {}, "ACCEPT", "OK"),
    ("terima foto saja", dict(barcode=NO_BARCODE, pred=photo("prod_a", 0.90)), "ACCEPT", "OK"),
    ("kuota habis", dict(deposits_today=3), "REJECT", "QUOTA"),
    ("aerosol", dict(pred=photo("aerosol_inhaler", 0.80)), "REJECT", "PROHIBITED"),
    ("bukan obat", dict(pred=photo("non_drug", 0.95)), "REJECT", "UNIDENTIFIED"),
    ("keyakinan di bawah floor", dict(pred=photo("prod_a", 0.40)), "REJECT", "UNIDENTIFIED"),
    ("kelas tak dikenal", dict(pred=photo("kelas_lain", 0.99)), "REJECT", "UNIDENTIFIED"),
    ("barcode tak terbaca", dict(barcode=BARCODE_UNREADABLE), "REJECT", "BARCODE_INVALID"),
    ("barcode tak terdaftar", dict(barcode=BARCODE_UNKNOWN), "REJECT", "BARCODE_INVALID"),
    ("barcode A, foto B", dict(pred=photo("prod_b", 0.95), weight_g=10.0), "REJECT", "MISMATCH"),
    ("keyakinan rendah dengan barcode", dict(pred=photo("prod_a", 0.55)), "REJECT", "LOW_CONFIDENCE"),
    ("keyakinan rendah foto saja", dict(barcode=NO_BARCODE, pred=photo("prod_a", 0.80)), "REJECT", "LOW_CONFIDENCE"),
    ("kemasan kosong persis tare", dict(weight_g=10.0), "REJECT", "WEIGHT_EMPTY"),
    ("lebih ringan dari kemasan kosong", dict(weight_g=2.0), "REJECT", "WEIGHT_EMPTY"),
    ("berat nol", dict(weight_g=0.0), "REJECT", "WEIGHT_EMPTY"),
    ("berat tidak ada", dict(weight_g=None), "REJECT", "WEIGHT_EMPTY"),
    ("berat NaN", dict(weight_g=float("nan")), "REJECT", "WEIGHT_EMPTY"),
    ("terlalu berat (isi diganti batu)", dict(weight_g=500.0), "REJECT", "WEIGHT_OVER"),

    # --- urutan aturan: aturan yang lebih awal menang ---
    ("kuota mengalahkan aerosol", dict(deposits_today=3, pred=photo("aerosol_inhaler", 0.99)), "REJECT", "QUOTA"),
    ("aerosol mengalahkan barcode valid", dict(pred=photo("aerosol_inhaler", 0.70), barcode=BARCODE_A), "REJECT", "PROHIBITED"),
    ("aerosol ragu-ragu jadi tak teridentifikasi", dict(pred=photo("aerosol_inhaler", 0.45)), "REJECT", "UNIDENTIFIED"),
    ("tak teridentifikasi mengalahkan barcode rusak", dict(pred=photo("non_drug", 0.90), barcode=BARCODE_UNREADABLE), "REJECT", "UNIDENTIFIED"),
    ("barcode tak terdaftar mengalahkan beda produk", dict(pred=photo("prod_b", 0.95), barcode=BARCODE_UNKNOWN), "REJECT", "BARCODE_INVALID"),
    ("beda produk mengalahkan keyakinan rendah", dict(pred=photo("prod_b", 0.55), barcode=BARCODE_A), "REJECT", "MISMATCH"),
    ("keyakinan rendah mengalahkan berat", dict(pred=photo("prod_a", 0.55), weight_g=500.0), "REJECT", "LOW_CONFIDENCE"),
    ("barcode benar tidak otomatis lolos berat", dict(barcode=BARCODE_A, weight_g=999.0), "REJECT", "WEIGHT_OVER"),
    ("barcode benar tidak meloloskan kemasan kosong", dict(barcode=BARCODE_A, weight_g=10.2), "REJECT", "WEIGHT_EMPTY"),

    # --- batas threshold (aturan memakai '<', jadi tepat di batas = lolos) ---
    ("kuota tepat di bawah batas", dict(deposits_today=2), "ACCEPT", "OK"),
    ("keyakinan tepat di floor, dengan barcode", dict(pred=photo("prod_a", 0.50)), "REJECT", "LOW_CONFIDENCE"),
    ("keyakinan tepat threshold barcode", dict(pred=photo("prod_a", 0.60)), "ACCEPT", "OK"),
    ("keyakinan sedikit di bawah threshold barcode", dict(pred=photo("prod_a", 0.5999)), "REJECT", "LOW_CONFIDENCE"),
    ("keyakinan tepat threshold foto saja", dict(barcode=NO_BARCODE, pred=photo("prod_a", 0.85)), "ACCEPT", "OK"),
    ("keyakinan sedikit di bawah threshold foto saja", dict(barcode=NO_BARCODE, pred=photo("prod_a", 0.8499)), "REJECT", "LOW_CONFIDENCE"),
    ("aerosol tepat di floor", dict(pred=photo("aerosol_inhaler", 0.50)), "REJECT", "PROHIBITED"),

    # --- batas berat P-A (tare 10 g, bruto 50 g) ---
    # kosong bila <= 10 + 0,5 + 3% x 10 = 10,8 g; terlalu berat bila > 50 x 1,05 = 52,5 g
    ("tepat batas kosong", dict(weight_g=10.8), "REJECT", "WEIGHT_EMPTY"),
    ("sedikit di atas batas kosong (sisa obat sedikit)", dict(weight_g=10.81), "ACCEPT", "OK"),
    ("tepat batas atas", dict(weight_g=52.5), "ACCEPT", "OK"),
    ("sedikit di atas batas atas", dict(weight_g=52.51), "REJECT", "WEIGHT_OVER"),
]


@pytest.mark.parametrize("name, kwargs, decision, reason_code", CASES, ids=[c[0] for c in CASES])
def test_decision_table(name, kwargs, decision, reason_code):
    result = run(**kwargs)
    assert (result["decision"], result["reason_code"]) == (decision, reason_code)


def test_every_reason_code_is_covered():
    covered = {case[3] for case in CASES}
    assert covered == set(REASON_TEXTS)


def test_accept_awards_points_and_verified_product():
    result = run()
    assert result["points_awarded"] == 10
    assert result["verified_product_id"] == "P-A"
    assert result["reason_text"] == "Produk A terdeteksi. Terima kasih, poin berhasil ditambahkan."


@pytest.mark.parametrize("kwargs", [c[1] for c in CASES if c[2] == "REJECT"])
def test_reject_never_awards_points(kwargs):
    result = run(**kwargs)
    assert result["points_awarded"] == 0
    assert result["verified_product_id"] is None
    assert result["reason_text"]  # selalu ada penjelasan berbahasa Indonesia


def test_signals_explain_the_decision():
    result = run(pred={"class_id": "prod_a", "confidence": 0.93,
                       "probs": {"prod_a": 0.93, "prod_b": 0.04, "non_drug": 0.02, "aerosol_inhaler": 0.01}})
    s = result["signals"]
    assert s["photo"]["top3"] == [["prod_a", 0.93], ["prod_b", 0.04], ["non_drug", 0.02]]
    assert s["barcode"] == {"present": True, "decoded": "2000000000015", "symbology": "EAN_13",
                            "product_id": "P-A", "valid": True}
    assert (s["weight"]["tare_g"], s["weight"]["gross_g"]) == (10, 50)
    assert (s["weight"]["empty_limit_g"], s["weight"]["over_limit_g"]) == (10.8, 52.5)
    assert (s["weight"]["status"], s["weight"]["ok"]) == ("OK", True)


def test_signals_are_filled_even_when_rejected_early():
    s = run(deposits_today=3, barcode=BARCODE_UNKNOWN, weight_g=500.0)["signals"]
    assert s["barcode"]["valid"] is False
    assert (s["weight"]["status"], s["weight"]["ok"]) == ("OVER", False)


def test_unknown_product_has_no_weight_verdict():
    s = run(pred=photo("non_drug", 0.95))["signals"]
    assert (s["weight"]["status"], s["weight"]["empty_limit_g"]) == (None, None)


@pytest.mark.parametrize("weight_g, code", [(10.0, "WEIGHT_EMPTY"), (500.0, "WEIGHT_OVER")])
def test_weight_texts_name_the_product(weight_g, code):
    result = run(weight_g=weight_g)
    assert result["reason_code"] == code and "Produk A" in result["reason_text"]


def test_quota_text_mentions_limit():
    assert "3 kali per hari" in run(deposits_today=3)["reason_text"]


def test_decide_does_not_modify_inputs():
    pred = photo("prod_a", 0.93)
    products_before = {k: dict(v) for k, v in PRODUCTS.items()}
    run(pred=pred)
    assert pred == photo("prod_a", 0.93)
    assert PRODUCTS == products_before
