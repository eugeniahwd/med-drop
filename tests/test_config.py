"""Validasi config.yaml harus menolak nilai yang tidak masuk akal (fail-closed)."""

import copy

import pytest

from backend.config import ConfigError, load_classes, load_config, validate_classes, validate_config


def test_repo_config_is_valid():
    load_config()


@pytest.mark.parametrize("section, key, bad_value", [
    ("classifier", "backend", "random"),
    ("classifier", "threshold_with_barcode", 1.5),
    ("classifier", "min_confidence_floor", 0.9),   # lebih tinggi dari threshold_with_barcode
    ("weight", "empty_margin_g", -1),
    ("weight", "gross_tolerance_pct", "lima"),
    ("points", "daily_limit_deposits", 2.5),
    ("bin", "capacity_g", 0),
    ("bin", "alert_fill_pct", 120),
])
def test_invalid_values_are_rejected(section, key, bad_value):
    cfg = copy.deepcopy(load_config())
    cfg[section][key] = bad_value
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_missing_key_is_rejected():
    cfg = copy.deepcopy(load_config())
    del cfg["points"]["per_valid_deposit"]
    with pytest.raises(ConfigError):
        validate_config(cfg)


def test_repo_classes_are_valid():
    classes = load_classes()
    assert sum(c["kind"] == "product" for c in classes) == 5


@pytest.mark.parametrize("change", [
    lambda cs: cs.append(dict(cs[0])),                                  # class_id ganda
    lambda cs: cs[0].update(kind="obat"),                               # kind tidak dikenal
    lambda cs: cs[0].pop("product_id"),                                 # produk tanpa product_id
    lambda cs: cs[0].update(prohibited=True),                           # produk ditandai terlarang
    lambda cs: cs.remove(next(c for c in cs if c["kind"] == "reject")),  # tidak ada kelas reject
])
def test_invalid_classes_are_rejected(change):
    classes = copy.deepcopy(load_classes())
    change(classes)
    with pytest.raises(ConfigError):
        validate_classes(classes)
