"""Baca config.yaml, data/classes.json, dan file .env (kunci Supabase dan kunci perangkat)."""

import json
import os
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
CLASSES_PATH = ROOT_DIR / "data" / "classes.json"


def load_config(path=None):
    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if cfg["classifier"]["backend"] not in ("mock", "keras"):
        raise ValueError("classifier.backend harus 'mock' atau 'keras'")
    return cfg


def load_classes(path=None):
    return json.loads(Path(path or CLASSES_PATH).read_text(encoding="utf-8"))


def load_env(path=ROOT_DIR / ".env"):
    """Baca .env (baris KEY=VALUE) ke environment. Nilai yang sudah ada tidak ditimpa."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
