"""Memuat dan memvalidasi config.yaml.

Validasi dibuat ketat (fail-closed): konfigurasi yang tidak masuk akal
membuat server gagal start, bukan berjalan dengan nilai yang salah.
"""

from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"

VALID_BACKENDS = ("mock", "keras")


class ConfigError(ValueError):
    """Konfigurasi tidak valid."""


def load_config(path: Path | str | None = None) -> dict:
    """Baca config.yaml (atau `path`) lalu validasi. Mengembalikan dict."""
    path = Path(path) if path else CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict) -> None:
    try:
        clf = cfg["classifier"]
        backend = clf["backend"]
        t_barcode = clf["threshold_with_barcode"]
        t_photo = clf["threshold_photo_only"]
        floor = clf["min_confidence_floor"]
        tolerance = cfg["weight"]["tolerance_pct"]
        per_deposit = cfg["points"]["per_valid_deposit"]
        daily_limit = cfg["points"]["daily_limit_deposits"]
        capacity = cfg["bin"]["capacity_g"]
        alert_pct = cfg["bin"]["alert_fill_pct"]
    except (KeyError, TypeError) as e:
        raise ConfigError(f"Kunci wajib tidak ada di config.yaml: {e}") from e

    if backend not in VALID_BACKENDS:
        raise ConfigError(f"classifier.backend harus salah satu dari {VALID_BACKENDS}, bukan {backend!r}")
    for name, value in (("threshold_with_barcode", t_barcode), ("threshold_photo_only", t_photo),
                        ("min_confidence_floor", floor)):
        if not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
            raise ConfigError(f"classifier.{name} harus angka 0..1, bukan {value!r}")
    if floor > t_barcode or floor > t_photo:
        raise ConfigError("classifier.min_confidence_floor tidak boleh lebih besar dari threshold mana pun")
    if not isinstance(tolerance, (int, float)) or tolerance < 0:
        raise ConfigError(f"weight.tolerance_pct harus >= 0, bukan {tolerance!r}")
    for name, value in (("per_valid_deposit", per_deposit), ("daily_limit_deposits", daily_limit)):
        if not isinstance(value, int) or value < 0:
            raise ConfigError(f"points.{name} harus bilangan bulat >= 0, bukan {value!r}")
    if not isinstance(capacity, (int, float)) or capacity <= 0:
        raise ConfigError(f"bin.capacity_g harus > 0, bukan {capacity!r}")
    if not isinstance(alert_pct, (int, float)) or not 0 < alert_pct <= 100:
        raise ConfigError(f"bin.alert_fill_pct harus di antara 0 dan 100, bukan {alert_pct!r}")
