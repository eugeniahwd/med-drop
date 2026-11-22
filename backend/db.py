"""Akses database SQLite MedDrop. Semua SQL proyek ada di file ini.

Lapisan ini sengaja dipisah supaya pindah ke database lain (misalnya Supabase/
PostgreSQL) cukup dengan mengganti modul ini tanpa menyentuh logika lain.

Waktu disimpan sebagai teks ISO 8601 dalam WIB (UTC+7), misalnya
"2026-11-22T10:15:00+07:00". Dengan begitu, 10 karakter pertama selalu
berisi tanggal WIB, dan itulah dasar penghitungan batas setoran harian.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.config import ROOT_DIR

DEFAULT_DB_PATH = ROOT_DIR / "data" / "meddrop.db"
WIB = timezone(timedelta(hours=7), "WIB")

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id   TEXT PRIMARY KEY,
    display      TEXT NOT NULL,
    barcode      TEXT NOT NULL UNIQUE,
    tare_g       REAL NOT NULL,
    gross_g      REAL NOT NULL,
    CHECK (tare_g > 0 AND gross_g > tare_g)
);

CREATE TABLE IF NOT EXISTS members (
    token      TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bins (
    bin_id     TEXT PRIMARY KEY,
    location   TEXT NOT NULL,
    capacity_g REAL NOT NULL CHECK (capacity_g > 0),
    current_g  REAL NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'OK'
);

CREATE TABLE IF NOT EXISTS transactions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                 TEXT NOT NULL,
    bin_id             TEXT NOT NULL REFERENCES bins(bin_id),
    member_token       TEXT NOT NULL REFERENCES members(token),
    claimed_product_id TEXT,
    photo_class        TEXT,
    photo_conf         REAL,
    barcode_present    INTEGER NOT NULL,
    barcode_valid      INTEGER NOT NULL,
    weight_g           REAL,
    decision           TEXT NOT NULL CHECK (decision IN ('ACCEPT', 'REJECT')),
    reason_code        TEXT NOT NULL,
    photo_path         TEXT
);
CREATE INDEX IF NOT EXISTS idx_transactions_member_ts ON transactions(member_token, ts);

CREATE TABLE IF NOT EXISTS point_ledger (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    member_token   TEXT NOT NULL REFERENCES members(token),
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    points         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    bin_id   TEXT NOT NULL REFERENCES bins(bin_id),
    type     TEXT NOT NULL,
    detail   TEXT,
    resolved INTEGER NOT NULL DEFAULT 0
);
"""

TRANSACTION_FIELDS = (
    "ts", "bin_id", "member_token", "claimed_product_id", "photo_class", "photo_conf",
    "barcode_present", "barcode_valid", "weight_g", "decision", "reason_code", "photo_path",
)


def now_wib() -> datetime:
    return datetime.now(WIB)


def _bin_dict(row) -> dict:
    result = dict(row)
    result["fill_pct"] = round(row["current_g"] / row["capacity_g"] * 100, 1)
    return result


def format_ts(dt: datetime) -> str:
    """Ubah datetime (wajib ber-zona waktu) menjadi teks ISO dalam WIB."""
    if dt.tzinfo is None:
        raise ValueError("datetime harus punya zona waktu")
    return dt.astimezone(WIB).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str = DEFAULT_DB_PATH):
        self.path = Path(path)

    @contextmanager
    def _connect(self):
        """Koneksi per operasi. Commit bila sukses, rollback bila ada error."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ---------- data master (diisi seed) ----------

    def upsert_product(self, product: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO products (product_id, display, barcode, tare_g, gross_g)
                   VALUES (:product_id, :display, :barcode, :tare_g, :gross_g)
                   ON CONFLICT(product_id) DO UPDATE SET
                       display = excluded.display,
                       barcode = excluded.barcode,
                       tare_g = excluded.tare_g,
                       gross_g = excluded.gross_g""",
                product,
            )

    def upsert_member(self, token: str, created_at: datetime) -> None:
        """Tambah anggota bila belum ada. Anggota lama tidak diubah."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO members (token, created_at) VALUES (?, ?)",
                (token, format_ts(created_at)),
            )

    def upsert_bin(self, bin_id: str, location: str, capacity_g: float) -> None:
        """Tambah bin atau perbarui lokasi/kapasitas. Isi bin saat ini dipertahankan."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO bins (bin_id, location, capacity_g) VALUES (?, ?, ?)
                   ON CONFLICT(bin_id) DO UPDATE SET
                       location = excluded.location,
                       capacity_g = excluded.capacity_g""",
                (bin_id, location, capacity_g),
            )

    # ---------- baca ----------

    def get_products(self) -> dict[str, dict]:
        """Semua produk, dikunci dengan product_id."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY product_id").fetchall()
        return {row["product_id"]: dict(row) for row in rows}

    def get_member(self, token: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM members WHERE token = ?", (token,)).fetchone()
        return dict(row) if row else None

    def list_members(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM members ORDER BY token").fetchall()
        return [dict(row) for row in rows]

    def get_member_state(self, token: str, day: date | None = None) -> dict:
        """Total poin dan jumlah setoran DITERIMA pada `day` (tanggal WIB, default hari ini)."""
        day = day or now_wib().date()
        with self._connect() as conn:
            points_total = conn.execute(
                "SELECT COALESCE(SUM(points), 0) FROM point_ledger WHERE member_token = ?",
                (token,),
            ).fetchone()[0]
            deposits_today = conn.execute(
                """SELECT COUNT(*) FROM transactions
                   WHERE member_token = ? AND decision = 'ACCEPT' AND substr(ts, 1, 10) = ?""",
                (token, day.isoformat()),
            ).fetchone()[0]
        return {"token": token, "points_total": points_total, "deposits_today": deposits_today}

    def get_bin(self, bin_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM bins WHERE bin_id = ?", (bin_id,)).fetchone()
        return _bin_dict(row) if row else None

    def list_bins(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM bins ORDER BY bin_id").fetchall()
        return [_bin_dict(row) for row in rows]

    def list_transactions(self, limit: int = 100, decision: str | None = None,
                          reason_code: str | None = None) -> list[dict]:
        """Transaksi terbaru lebih dulu, bisa difilter keputusan dan/atau reason_code."""
        where, params = [], []
        if decision:
            where.append("decision = ?")
            params.append(decision)
        if reason_code:
            where.append("reason_code = ?")
            params.append(reason_code)
        sql = "SELECT * FROM transactions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(sql, (*params, limit)).fetchall()
        return [dict(row) for row in rows]

    def list_alerts(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM alerts ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    # ---------- agregat untuk dashboard ----------

    def transaction_totals(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS attempts,
                          COALESCE(SUM(decision = 'ACCEPT'), 0) AS accepted,
                          COALESCE(SUM(decision = 'REJECT'), 0) AS rejected
                   FROM transactions"""
            ).fetchone()
            points = conn.execute("SELECT COALESCE(SUM(points), 0) FROM point_ledger").fetchone()[0]
        return {**dict(row), "points_total": points}

    def accepted_count_by_photo_class(self) -> dict[str, int]:
        """Jumlah setoran DITERIMA per kelas foto (pada ACCEPT, kelas foto = produk terverifikasi)."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT photo_class, COUNT(*) FROM transactions
                   WHERE decision = 'ACCEPT' GROUP BY photo_class"""
            ).fetchall()
        return {row[0]: row[1] for row in rows}

    def rejected_count_by_reason(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT reason_code, COUNT(*) FROM transactions
                   WHERE decision = 'REJECT' GROUP BY reason_code"""
            ).fetchall()
        return {row[0]: row[1] for row in rows}

    # ---------- operasi admin (simulasi) ----------

    def empty_bin(self, bin_id: str) -> bool:
        """Kosongkan bin (simulasi penjemputan) dan selesaikan alert BIN_FULL-nya."""
        with self._connect() as conn:
            updated = conn.execute(
                "UPDATE bins SET current_g = 0, status = 'OK' WHERE bin_id = ?", (bin_id,)
            ).rowcount
            conn.execute(
                "UPDATE alerts SET resolved = 1 WHERE bin_id = ? AND type = 'BIN_FULL' AND resolved = 0",
                (bin_id,),
            )
        return updated > 0

    def create_alert(self, bin_id: str, alert_type: str, detail: str, ts: datetime | None = None) -> dict:
        with self._connect() as conn:
            alert_id = conn.execute(
                "INSERT INTO alerts (ts, bin_id, type, detail) VALUES (?, ?, ?, ?)",
                (format_ts(ts or now_wib()), bin_id, alert_type, detail),
            ).lastrowid
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return dict(row)

    # ---------- tulis transaksi ----------

    def record_attempt(self, tx: dict, points: int, alert_fill_pct: float) -> int:
        """Catat satu percobaan setor (diterima maupun ditolak) secara atomik.

        `tx` berisi kolom TRANSACTION_FIELDS; `tx["ts"]` berupa datetime ber-zona
        waktu atau None (sekarang). Hanya ACCEPT yang menambah poin dan isi bin.
        Bila kepenuhan bin mencapai `alert_fill_pct`, dibuat satu alert BIN_FULL
        (tidak berulang selama alert sebelumnya belum diselesaikan).
        Mengembalikan id transaksi.
        """
        accepted = tx["decision"] == "ACCEPT"
        if not accepted and points:
            raise ValueError("Poin hanya boleh diberikan untuk setoran yang diterima")
        row = {field: tx.get(field) for field in TRANSACTION_FIELDS}
        row["ts"] = format_ts(tx.get("ts") or now_wib())

        columns = ", ".join(TRANSACTION_FIELDS)
        placeholders = ", ".join(":" + field for field in TRANSACTION_FIELDS)
        with self._connect() as conn:
            tx_id = conn.execute(
                f"INSERT INTO transactions ({columns}) VALUES ({placeholders})", row
            ).lastrowid
            if accepted:
                if points:
                    conn.execute(
                        """INSERT INTO point_ledger (ts, member_token, transaction_id, points)
                           VALUES (?, ?, ?, ?)""",
                        (row["ts"], row["member_token"], tx_id, points),
                    )
                conn.execute(
                    "UPDATE bins SET current_g = current_g + ? WHERE bin_id = ?",
                    (row["weight_g"] or 0, row["bin_id"]),
                )
                self._raise_bin_full_alert(conn, row["bin_id"], alert_fill_pct, row["ts"])
        return tx_id

    @staticmethod
    def _raise_bin_full_alert(conn, bin_id: str, alert_fill_pct: float, ts: str) -> None:
        current_g, capacity_g = conn.execute(
            "SELECT current_g, capacity_g FROM bins WHERE bin_id = ?", (bin_id,)
        ).fetchone()
        fill_pct = current_g / capacity_g * 100
        if fill_pct < alert_fill_pct:
            return
        already_open = conn.execute(
            "SELECT 1 FROM alerts WHERE bin_id = ? AND type = 'BIN_FULL' AND resolved = 0",
            (bin_id,),
        ).fetchone()
        if not already_open:
            conn.execute(
                "INSERT INTO alerts (ts, bin_id, type, detail) VALUES (?, ?, 'BIN_FULL', ?)",
                (ts, bin_id, f"Fill level {fill_pct:.1f}% (threshold {alert_fill_pct}%)"),
            )
        conn.execute("UPDATE bins SET status = 'FULL' WHERE bin_id = ?", (bin_id,))
