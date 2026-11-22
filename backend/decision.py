"""Engine keputusan MedDrop: fungsi murni tanpa akses database, file, atau jam.

Keputusan dihitung hanya dari sinyal (foto, barcode, berat) dan kuota anggota.
Aturan diperiksa berurutan dan berhenti di aturan pertama yang gagal (fail-closed):

    1. QUOTA            setoran diterima hari ini >= batas harian
    2. PROHIBITED       kelas foto terlarang (aerosol/inhaler) dengan keyakinan >= floor
    3. UNIDENTIFIED     kelas foto 'reject' (non_drug), kelas tak dikenal, atau keyakinan < floor
    4. dengan barcode:  BARCODE_INVALID -> MISMATCH -> LOW_CONFIDENCE (< threshold_with_barcode)
       tanpa barcode:   LOW_CONFIDENCE (< threshold_photo_only)
    5. WEIGHT_EMPTY     berat <= tare + margin: kemasan kosong atau tidak lengkap
       WEIGHT_OVER      berat > bruto + toleransi: terlalu berat (isi mungkin diganti benda lain)
    6. ACCEPT

Barcode hanyalah klaim identitas; foto dan berat adalah pembuktiannya.
"""

import math

ACCEPT = "ACCEPT"
REJECT = "REJECT"

REASON_TEXTS = {
    "OK": "{product} terdeteksi. Terima kasih, poin berhasil ditambahkan.",
    "QUOTA": "Batas setoran harian Anda ({limit} kali per hari) sudah tercapai. "
             "Silakan ambil kembali barang Anda dan setor lagi besok.",
    "PROHIBITED": "Aerosol dan inhaler tidak dapat diterima karena kemasannya bertekanan. "
                  "Silakan ambil kembali barang Anda dan serahkan langsung ke petugas apotek.",
    "UNIDENTIFIED": "Barang tidak dapat diidentifikasi. Silakan bawa ke apotek, "
                    "atau ikuti panduan pemusnahan obat di rumah dari Kemenkes.",
    "BARCODE_INVALID": "Barcode tidak dikenali sebagai produk yang diterima mesin ini. "
                       "Silakan ambil kembali barang Anda dan bawa ke apotek.",
    "MISMATCH": "Barcode tidak cocok dengan kemasan yang terlihat di kamera. "
                "Silakan ambil kembali barang Anda lalu coba lagi.",
    "LOW_CONFIDENCE": "Kemasan belum dapat dikenali dengan yakin. Silakan ambil kembali barang Anda, "
                      "letakkan dengan sisi depan menghadap kamera, lalu coba lagi.",
    "WEIGHT_EMPTY": "Kemasan {product} tampak kosong atau tidak lengkap. Mesin hanya menerima obat yang masih "
                    "berisi dan disetor bersama kemasan jualnya (dus atau botol). Silakan ambil kembali barang Anda.",
    "WEIGHT_OVER": "Berat barang melebihi berat wajar {product} dalam kemasan penuh. "
                   "Silakan ambil kembali barang Anda.",
}


def decide(member_state: dict, photo_pred: dict, barcode_result: dict, weight_g,
           config: dict, products: dict, classes: list) -> dict:
    """Hitung keputusan untuk satu setoran.

    member_state   {"deposits_today": int, ...}
    photo_pred     hasil classifier: {"class_id", "confidence", "probs"}
    barcode_result hasil barcode_reader: {"present", "decoded", "symbology", ...}
    weight_g       berat terukur (gram)
    products       {product_id: {"display", "barcode", "tare_g", "gross_g", ...}}
    classes        isi classes.json

    Mengembalikan {"decision", "reason_code", "reason_text", "signals",
                   "points_awarded", "verified_product_id"}.
    """
    clf_cfg = config["classifier"]
    floor = clf_cfg["min_confidence_floor"]
    classes_by_id = {c["class_id"]: c for c in classes}
    product_id_by_barcode = {p["barcode"]: pid for pid, p in products.items()}

    photo_class = classes_by_id.get(photo_pred["class_id"])
    confidence = float(photo_pred["confidence"])
    photo_product_id = photo_class.get("product_id") if photo_class and photo_class["kind"] == "product" else None
    photo_product = products.get(photo_product_id) if photo_product_id else None

    barcode_present = bool(barcode_result.get("present"))
    decoded = barcode_result.get("decoded") if barcode_present else None
    barcode_product_id = product_id_by_barcode.get(decoded) if decoded else None

    signals = {
        "photo": {
            "class_id": photo_pred["class_id"],
            "display": photo_class["display"] if photo_class else None,
            "confidence": confidence,
            "top3": top_k(photo_pred.get("probs", {}), 3),
        },
        "barcode": {
            "present": barcode_present,
            "decoded": decoded,
            "symbology": barcode_result.get("symbology") if barcode_present else None,
            "product_id": barcode_product_id,
            "valid": (barcode_product_id is not None) if barcode_present else None,
        },
        "weight": weight_signal(weight_g, photo_product, config["weight"]),
    }

    def reject(code, **fmt):
        return _result(REJECT, code, signals, points=0, product_id=None, **fmt)

    if member_state["deposits_today"] >= config["points"]["daily_limit_deposits"]:
        return reject("QUOTA", limit=config["points"]["daily_limit_deposits"])
    if photo_class and photo_class["prohibited"] and confidence >= floor:
        return reject("PROHIBITED")
    if photo_product is None or confidence < floor:
        # Kelas 'reject', kelas tak dikenal, kelas terlarang berkeyakinan rendah,
        # atau keyakinan di bawah floor: semuanya dianggap tidak teridentifikasi.
        return reject("UNIDENTIFIED")

    if barcode_present:
        if barcode_product_id is None:
            return reject("BARCODE_INVALID")
        if barcode_product_id != photo_product_id:
            return reject("MISMATCH")
        if confidence < clf_cfg["threshold_with_barcode"]:
            return reject("LOW_CONFIDENCE")
    elif confidence < clf_cfg["threshold_photo_only"]:
        return reject("LOW_CONFIDENCE")

    if signals["weight"]["status"] == "EMPTY":
        return reject("WEIGHT_EMPTY", product=photo_product["display"])
    if signals["weight"]["status"] == "OVER":
        return reject("WEIGHT_OVER", product=photo_product["display"])

    return _result(ACCEPT, "OK", signals, points=config["points"]["per_valid_deposit"],
                   product_id=photo_product_id, product=photo_product["display"])


def weight_signal(weight_g, product: dict | None, weight_cfg: dict) -> dict:
    """Bandingkan berat terukur dengan tare (kemasan kosong) dan bruto (kemasan penuh) produk.

    status: "EMPTY" bila berat <= batas kosong (termasuk berat tidak valid atau <= 0),
            "OVER" bila berat > batas atas, "OK" di antaranya, None bila produk belum diketahui.
    """
    signal = {"measured_g": weight_g, "tare_g": None, "gross_g": None,
              "empty_limit_g": None, "over_limit_g": None, "status": None, "ok": None}
    if product is None:
        return signal
    tare, gross = product["tare_g"], product["gross_g"]
    empty_limit = round(tare + weight_cfg["empty_margin_g"] + tare * weight_cfg["empty_margin_pct"] / 100, 3)
    over_limit = round(gross * (100 + weight_cfg["gross_tolerance_pct"]) / 100, 3)
    measured = isinstance(weight_g, (int, float)) and math.isfinite(weight_g) and weight_g > 0
    if not measured or weight_g <= empty_limit:
        status = "EMPTY"
    elif weight_g > over_limit:
        status = "OVER"
    else:
        status = "OK"
    signal.update(tare_g=tare, gross_g=gross, empty_limit_g=empty_limit, over_limit_g=over_limit,
                  status=status, ok=status == "OK")
    return signal


def top_k(probs: dict, k: int) -> list:
    return [[cid, p] for cid, p in sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:k]]


def _result(decision, reason_code, signals, points, product_id, **fmt):
    return {
        "decision": decision,
        "reason_code": reason_code,
        "reason_text": REASON_TEXTS[reason_code].format(**fmt),
        "signals": signals,
        "points_awarded": points,
        "verified_product_id": product_id,
    }
