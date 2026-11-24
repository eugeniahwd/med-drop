"""Kirim data dari ESP32 ke Supabase lewat REST API.

Hanya server yang memegang kunci Supabase (di .env); ESP32 tidak pernah menyimpannya.
Kalau Supabase belum diatur atau sedang tidak terjangkau, keputusan tetap dikirim
ke ESP32 dan server hanya mencetak peringatan.
"""

import os
from datetime import datetime, timezone

import httpx


def save_heartbeat(device_id, rssi=None, uptime_s=None, firmware=None, ip=None):
    row = {"device_id": device_id, "last_seen": datetime.now(timezone.utc).isoformat(),
           "rssi": rssi, "uptime_s": uptime_s, "firmware": firmware, "ip": ip}
    # upsert: satu baris per perangkat, last_seen selalu diperbarui
    return _post("devices", row, "resolution=merge-duplicates,return=minimal", {"on_conflict": "device_id"})


def save_transaction(row):
    return _post("device_transactions", row, "return=minimal")


def _post(table, row, prefer, params=None):
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        print("Supabase belum diatur di .env, data perangkat tidak dikirim ke cloud.")
        return False
    headers = {"apikey": key, "Content-Type": "application/json", "Prefer": prefer}
    if key.startswith("eyJ"):  # kunci format lama (JWT) juga dikirim sebagai Bearer
        headers["Authorization"] = f"Bearer {key}"
    try:
        r = httpx.post(f"{url}/rest/v1/{table}", params=params, json=row, headers=headers, timeout=10)
        r.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        print(f"Supabase menolak data {table}: {e.response.status_code} {e.response.text[:200]}")
    except httpx.HTTPError as e:
        print(f"Supabase tidak terjangkau ({table}): {e}")
    return False
