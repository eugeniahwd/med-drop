"""Tes lapisan data: hanya ACCEPT yang mengubah poin/kuota/bin, kuota dihitung per hari WIB."""

import sqlite3
from datetime import date, datetime, timezone

import pytest

from backend.db import WIB, Database

DAY = date(2026, 11, 22)
NOON = datetime(2026, 11, 22, 12, 0, tzinfo=WIB)


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    d.init_schema()
    d.upsert_product({"product_id": "P-T", "display": "Produk uji", "barcode": "2000000000015",
                      "tare_g": 10, "gross_g": 50})
    d.upsert_member("MBR-T1", NOON)
    d.upsert_bin("BIN-T", "Lokasi uji", capacity_g=1000)
    return d


def attempt(decision, weight_g=40.0, ts=NOON):
    return {
        "ts": ts, "bin_id": "BIN-T", "member_token": "MBR-T1", "claimed_product_id": "P-T",
        "photo_class": "entrostop", "photo_conf": 0.9, "barcode_present": True, "barcode_valid": True,
        "weight_g": weight_g, "decision": decision,
        "reason_code": "OK" if decision == "ACCEPT" else "WEIGHT_OVER", "photo_path": None,
    }


def test_accept_adds_points_quota_and_bin_weight(db):
    db.record_attempt(attempt("ACCEPT"), points=10, alert_fill_pct=80)
    assert db.get_member_state("MBR-T1", DAY) == {"token": "MBR-T1", "points_total": 10, "deposits_today": 1}
    assert db.get_bin("BIN-T")["current_g"] == 40.0
    assert db.get_bin("BIN-T")["fill_pct"] == 4.0


def test_reject_is_recorded_but_changes_nothing_else(db):
    db.record_attempt(attempt("REJECT"), points=0, alert_fill_pct=80)
    assert len(db.list_transactions()) == 1
    assert db.get_member_state("MBR-T1", DAY) == {"token": "MBR-T1", "points_total": 0, "deposits_today": 0}
    assert db.get_bin("BIN-T")["current_g"] == 0


def test_reject_with_points_is_refused_and_not_written(db):
    with pytest.raises(ValueError):
        db.record_attempt(attempt("REJECT"), points=10, alert_fill_pct=80)
    assert db.list_transactions() == []


def test_daily_quota_follows_wib_calendar_day(db):
    # 23:30 WIB tanggal 21 masih dihitung tanggal 21.
    db.record_attempt(attempt("ACCEPT", ts=datetime(2026, 11, 21, 23, 30, tzinfo=WIB)), 10, 80)
    # 17:30 UTC tanggal 21 = 00:30 WIB tanggal 22.
    db.record_attempt(attempt("ACCEPT", ts=datetime(2026, 11, 21, 17, 30, tzinfo=timezone.utc)), 10, 80)
    assert db.get_member_state("MBR-T1", date(2026, 11, 21))["deposits_today"] == 1
    assert db.get_member_state("MBR-T1", date(2026, 11, 22))["deposits_today"] == 1
    assert db.get_member_state("MBR-T1", DAY)["points_total"] == 20


def test_bin_full_alert_is_raised_once(db):
    for _ in range(3):  # 45%, 90%, 135% dari kapasitas 1000 g
        db.record_attempt(attempt("ACCEPT", weight_g=450), points=10, alert_fill_pct=80)
    alerts = db.list_alerts()
    assert [a["type"] for a in alerts] == ["BIN_FULL"]
    assert alerts[0]["resolved"] == 0
    assert db.get_bin("BIN-T")["status"] == "FULL"


def test_naive_datetime_is_rejected(db):
    with pytest.raises(ValueError):
        db.record_attempt(attempt("ACCEPT", ts=datetime(2026, 11, 22, 12, 0)), 10, 80)


def test_unknown_member_is_rejected_by_foreign_key(db):
    tx = attempt("REJECT") | {"member_token": "MBR-TIDAK-ADA"}
    with pytest.raises(sqlite3.IntegrityError):
        db.record_attempt(tx, points=0, alert_fill_pct=80)
