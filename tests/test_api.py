"""Tes API end-to-end dengan MockClassifier, foto split test, dan gambar barcode asli proyek.

Setiap tes memakai database sementara yang diisi persis seperti scripts/seed_db.py.
"""

import pytest
from fastapi.testclient import TestClient

from backend.config import load_classes, load_config
from backend.db import Database, now_wib
from backend.main import create_app
from backend.seed import load_seed_files, seed

BIN = "BIN-001"


@pytest.fixture
def env(tmp_path):
    cfg, classes = load_config(), load_classes()
    cfg["classifier"]["backend"] = "mock"  # tes API selalu memakai mock, apa pun isi config.yaml
    products, members = load_seed_files()
    db = Database(tmp_path / "test.db")
    seed(db, cfg, classes, products, members)
    for i in range(1, 21):  # anggota uji tambahan agar kuota tidak membatasi tes
        db.upsert_member(f"MBR-T{i:02d}", now_wib())
    client = TestClient(create_app(config=cfg, db=db, classes=classes, uploads_dir=tmp_path / "uploads"))
    return client, db, tmp_path


def post_verify(client, item, member="MBR-0001", weight_g=None, barcode=True, barcode_text=None):
    files = {"photo": ("foto.jpg", client.get(item["photo_url"]).content, "image/jpeg")}
    if barcode and item["barcode_image_url"]:
        files["barcode_image"] = ("barcode.png", client.get(item["barcode_image_url"]).content, "image/png")
    data = {"member_token": member, "bin_id": BIN,
            "weight_g": str(item["weight_g"] if weight_g is None else weight_g)}
    if barcode_text:
        data["barcode_text"] = barcode_text
    return client.post("/api/verify", data=data, files=files)


def items(client):
    return {i["item_id"]: i for i in client.get("/api/items").json()}


# ---------- endpoint baca ----------

def test_config_reports_mock_classifier(env):
    client, _, _ = env
    clf = client.get("/api/config").json()["classifier"]
    assert (clf["backend"], clf["is_mock"]) == ("mock", True)


def test_items_photos_and_barcodes_are_served(env):
    client, _, _ = env
    cards = client.get("/api/items").json()
    assert len(cards) >= 10
    for card in cards:
        assert card["photo"].startswith(("dataset/test/", "dataset/test_degraded/"))
        assert client.get(card["photo_url"]).status_code == 200
        if card["barcode_image_url"]:
            assert client.get(card["barcode_image_url"]).status_code == 200


def test_member_state_and_unknown_member(env):
    client, _, _ = env
    assert client.get("/api/members/MBR-0001").json() == {
        "token": "MBR-0001", "points_total": 0, "deposits_today": 0, "daily_limit": 3, "remaining_today": 3}
    assert client.get("/api/members/MBR-0003").json()["remaining_today"] == 0
    r = client.get("/api/members/MBR-9999")
    assert r.status_code == 404 and r.json()["detail"] == "Member number not recognized."


def test_frontend_is_served_at_root(env):
    client, _, _ = env
    assert client.get("/").status_code == 200


# ---------- alur /api/verify ----------

def test_every_card_matches_its_scenario(env):
    client, _, _ = env
    for n, card in enumerate(items(client).values(), start=1):
        r = post_verify(client, card, member=f"MBR-T{n:02d}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert (body["decision"], body["reason_code"]) == (card["expected_decision"], card["expected_reason"]), \
            f"{card['item_id']} {card['label']}: {body['reason_code']} ({body['signals']['photo']})"


def test_accept_response_matches_schema_and_updates_state(env):
    client, _, tmp_path = env
    bin_before = client.get(f"/api/bins/{BIN}").json()["current_g"]
    body = post_verify(client, items(client)["it-001"]).json()

    assert (body["decision"], body["reason_code"], body["points_awarded"]) == ("ACCEPT", "OK", 10)
    assert body["reason_text"].startswith("Entrostop recognized")
    s = body["signals"]
    assert s["photo"]["class_id"] == "entrostop" and len(s["photo"]["top3"]) == 3
    assert s["barcode"] == {"present": True, "decoded": "2000000000015", "symbology": "EAN_13",
                            "product_id": "P-A", "valid": True}
    assert (s["weight"]["status"], s["weight"]["measured_g"]) == ("OK", 20.0)
    assert body["member"] == {"token": "MBR-0001", "points_total": 10, "deposits_today": 1,
                              "daily_limit": 3, "remaining_today": 2}
    assert body["bin"]["current_g"] == bin_before + 20.0

    tx = client.get("/api/admin/transactions").json()[0]
    assert tx["id"] == body["transaction_id"]
    assert (tx["member_token"], tx["claimed_product_id"], tx["photo_class"], tx["decision"]) == \
           ("MBR-0001", "P-A", "entrostop", "ACCEPT")
    assert (tmp_path / tx["photo_path"]).is_file()


def test_reject_is_recorded_without_points(env):
    client, _, _ = env
    body = post_verify(client, items(client)["it-006"]).json()  # isi diganti benda berat
    assert (body["decision"], body["reason_code"], body["points_awarded"]) == ("REJECT", "WEIGHT_OVER", 0)
    assert body["member"]["points_total"] == 0 and body["member"]["deposits_today"] == 0
    tx = client.get("/api/admin/transactions").json()[0]
    assert (tx["id"], tx["decision"], tx["reason_code"]) == (body["transaction_id"], "REJECT", "WEIGHT_OVER")


def test_quota_member_is_rejected(env):
    client, _, _ = env
    body = post_verify(client, items(client)["it-001"], member="MBR-0003").json()
    assert (body["decision"], body["reason_code"]) == ("REJECT", "QUOTA")


def test_barcode_text_from_scanner_is_accepted(env):
    client, _, _ = env
    body = post_verify(client, items(client)["it-001"], barcode=False, barcode_text="2000000000015").json()
    assert (body["reason_code"], body["signals"]["barcode"]["symbology"]) == ("OK", "TEXT")


# ---------- pemeriksaan sebelum pintu dibuka: tanpa transaksi ----------

def test_unknown_member_is_refused_without_transaction(env):
    client, _, _ = env
    r = post_verify(client, items(client)["it-001"], member="MBR-9999")
    assert r.status_code == 404
    assert client.get("/api/admin/transactions").json()[0]["member_token"] == "MBR-0003"  # hanya data seed


def test_full_bin_is_refused_without_transaction_until_emptied(env):
    client, db, _ = env
    db.record_attempt({"ts": now_wib(), "bin_id": BIN, "member_token": "MBR-0002", "barcode_present": False,
                       "barcode_valid": False, "weight_g": 5000, "decision": "ACCEPT", "reason_code": "OK"},
                      points=0, alert_fill_pct=80)
    count = len(client.get("/api/admin/transactions").json())
    assert client.get(f"/api/bins/{BIN}").json()["accepting"] is False

    r = post_verify(client, items(client)["it-001"])
    assert r.status_code == 409 and r.json()["detail"] == "This machine is full. Please use another drop-off point."
    assert len(client.get("/api/admin/transactions").json()) == count
    assert [a["type"] for a in client.get("/api/admin/alerts").json() if not a["resolved"]] == ["BIN_FULL"]

    emptied = client.post(f"/api/admin/bins/{BIN}/empty").json()
    assert (emptied["current_g"], emptied["status"], emptied["accepting"]) == (0, "OK", True)
    assert all(a["resolved"] for a in client.get("/api/admin/alerts").json())
    assert post_verify(client, items(client)["it-001"]).status_code == 200


@pytest.mark.parametrize("weight_g", ["nan", "inf", "berat"])
def test_invalid_weight_is_rejected_as_bad_input(env, weight_g):
    client, _, _ = env
    assert post_verify(client, items(client)["it-001"], weight_g=weight_g).status_code == 422


def test_unreadable_photo_is_rejected_as_bad_input(env):
    client, _, _ = env
    r = client.post("/api/verify", data={"member_token": "MBR-0001", "bin_id": BIN, "weight_g": "20"},
                    files={"photo": ("foto.jpg", b"bukan gambar", "image/jpeg")})
    assert r.status_code == 422


# ---------- dashboard admin ----------

def test_stats_and_filters(env):
    client, _, _ = env
    cards = items(client)
    post_verify(client, cards["it-001"], member="MBR-T01")   # ACCEPT entrostop
    post_verify(client, cards["it-003"], member="MBR-T02")   # ACCEPT kalpanax
    post_verify(client, cards["it-005"], member="MBR-T03")   # REJECT WEIGHT_EMPTY
    post_verify(client, cards["it-007"], member="MBR-T04")   # REJECT MISMATCH

    stats = client.get("/api/admin/stats").json()
    by_product = {p["class_id"]: p["count"] for p in stats["accepted_by_product"]}
    # 3 setoran contoh MBR-0003 dari seed: entrostop, fatigon, kalpanax
    assert by_product == {"entrostop": 2, "fatigon": 1, "kalpanax": 2, "promag": 0, "woods": 0}
    by_reason = {r["reason_code"]: r["count"] for r in stats["rejected_by_reason"]}
    assert by_reason["WEIGHT_EMPTY"] == 1 and by_reason["MISMATCH"] == 1 and by_reason["QUOTA"] == 0
    assert stats["totals"] == {"attempts": 7, "accepted": 5, "rejected": 2, "points_total": 50}
    assert stats["bins"][0]["bin_id"] == BIN

    rejects = client.get("/api/admin/transactions", params={"decision": "REJECT"}).json()
    assert {t["reason_code"] for t in rejects} == {"WEIGHT_EMPTY", "MISMATCH"}
    only = client.get("/api/admin/transactions", params={"reason_code": "MISMATCH"}).json()
    assert [t["reason_code"] for t in only] == ["MISMATCH"]


def test_tamper_creates_alert(env):
    client, _, _ = env
    alert = client.post(f"/api/admin/bins/{BIN}/tamper").json()
    assert (alert["type"], alert["resolved"]) == ("TAMPER", False)
    assert client.get("/api/admin/alerts").json()[0]["id"] == alert["id"]
    assert client.post("/api/admin/bins/BIN-XXX/tamper").status_code == 404


# ---------- endpoint ESP32 ----------

def test_device_endpoints_need_the_device_key(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setenv("DEVICE_KEY", "kunci-uji")
    assert client.post("/api/device/heartbeat", json={"device_id": BIN}).status_code == 401
    r = client.post("/api/device/heartbeat", json={"device_id": BIN}, headers={"X-Device-Key": "salah"})
    assert r.status_code == 401


def test_device_verify_answers_briefly_and_sends_a_copy_to_cloud(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setenv("DEVICE_KEY", "kunci-uji")
    sent = []
    monkeypatch.setattr("backend.cloud.save_transaction", lambda row: sent.append(row) or True)
    card = items(client)["it-001"]
    r = client.post("/api/device/verify", headers={"X-Device-Key": "kunci-uji"},
                    data={"member_token": "MBR-0001", "bin_id": BIN, "weight_g": "20", "barcode_text": "2000000000015"},
                    files={"photo": ("foto.jpg", client.get(card["photo_url"]).content, "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["decision"] == "ACCEPT" and r.json()["product"] == "Entrostop"
    assert sent[0]["device_id"] == BIN and sent[0]["decision"] == "ACCEPT" and sent[0]["barcode"] == "2000000000015"


def test_heartbeat_goes_to_cloud(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setenv("DEVICE_KEY", "kunci-uji")
    beats = []
    monkeypatch.setattr("backend.cloud.save_heartbeat", lambda **beat: beats.append(beat) or True)
    r = client.post("/api/device/heartbeat", headers={"X-Device-Key": "kunci-uji"},
                    json={"device_id": BIN, "rssi": -60, "uptime_s": 42, "firmware": "0.1.0"})
    assert r.json() == {"ok": True, "saved_to_cloud": True}
    assert beats[0]["device_id"] == BIN and beats[0]["rssi"] == -60
