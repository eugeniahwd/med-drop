"""Validasi config.yaml harus menolak nilai yang tidak masuk akal (fail-closed)."""

import copy

import pytest

from backend.config import ConfigError, load_config, validate_config


def test_repo_config_is_valid():
    load_config()


@pytest.mark.parametrize("section, key, bad_value", [
    ("classifier", "backend", "random"),
    ("classifier", "threshold_with_qr", 1.5),
    ("classifier", "min_confidence_floor", 0.9),   # lebih tinggi dari threshold_with_qr
    ("weight", "tolerance_pct", -1),
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
