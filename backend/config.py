"""Memuat dan memvalidasi config.yaml.

Validasi dibuat ketat (fail-closed): konfigurasi yang tidak masuk akal
membuat server gagal start, bukan berjalan dengan nilai yang salah.
"""

import json
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
CLASSES_PATH = ROOT_DIR / "data" / "classes.json"

VALID_BACKENDS = ("mock", "keras")
VALID_CLASS_KINDS = ("product", "reject", "prohibited")


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
        weight_values = {k: cfg["weight"][k] for k in ("empty_margin_g", "empty_margin_pct", "gross_tolerance_pct")}
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
    for name, value in weight_values.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigError(f"weight.{name} harus angka >= 0, bukan {value!r}")
    for name, value in (("per_valid_deposit", per_deposit), ("daily_limit_deposits", daily_limit)):
        if not isinstance(value, int) or value < 0:
            raise ConfigError(f"points.{name} harus bilangan bulat >= 0, bukan {value!r}")
    if not isinstance(capacity, (int, float)) or capacity <= 0:
        raise ConfigError(f"bin.capacity_g harus > 0, bukan {capacity!r}")
    if not isinstance(alert_pct, (int, float)) or not 0 < alert_pct <= 100:
        raise ConfigError(f"bin.alert_fill_pct harus di antara 0 dan 100, bukan {alert_pct!r}")


def load_classes(path: Path | str | None = None) -> list[dict]:
    """Baca data/classes.json (atau `path`) lalu validasi."""
    path = Path(path) if path else CLASSES_PATH
    classes = json.loads(path.read_text(encoding="utf-8"))
    validate_classes(classes)
    return classes


def validate_classes(classes: list[dict]) -> None:
    ids = [c.get("class_id") for c in classes]
    if len(set(ids)) != len(ids):
        raise ConfigError("Ada class_id ganda di classes.json")
    for c in classes:
        kind = c.get("kind")
        if kind not in VALID_CLASS_KINDS:
            raise ConfigError(f"Kelas {c.get('class_id')!r}: kind harus salah satu dari {VALID_CLASS_KINDS}")
        if kind == "product" and not c.get("product_id"):
            raise ConfigError(f"Kelas produk {c['class_id']!r} wajib punya product_id")
        if c.get("prohibited") is not (kind == "prohibited"):
            raise ConfigError(f"Kelas {c['class_id']!r}: prohibited harus true hanya untuk kind 'prohibited'")
    if not any(c["kind"] == "reject" for c in classes):
        raise ConfigError("classes.json wajib punya satu kelas kind 'reject' (mis. non_drug)")
