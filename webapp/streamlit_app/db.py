"""Log aktivitas (SQLite ringan) — satu-satunya penggunaan database di aplikasi.

Sesuai PRD: database tidak pernah menyimpan data harga, komoditas, hasil
prediksi, maupun akun. Hanya audit ringan — log login/logout admin (tanpa
tabel `users`, identitas cukup peran "admin") dan nantinya log prediksi
publik anonim (ditambahkan pada task tersendiri).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).parent / "tracking.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waktu TEXT NOT NULL,
            aksi TEXT NOT NULL,
            sesi TEXT NOT NULL
        )
        """
    )
    return conn


def catat_aktivitas_admin(aksi: str, sesi: str) -> None:
    """Catat satu baris log login/logout admin.

    `aksi`: "login" atau "logout". `sesi`: penanda sesi tab admin, supaya
    pasangan login-logout yang sama bisa dikorelasikan saat audit.
    """
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO admin_login_logs (waktu, aksi, sesi) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), aksi, sesi),
        )


def ambil_log_admin(batas: int = 50) -> list[sqlite3.Row]:
    """Baris log terbaru dulu — dipakai untuk audit di panel admin bila perlu."""
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT waktu, aksi, sesi FROM admin_login_logs ORDER BY id DESC LIMIT ?",
            (batas,),
        ).fetchall()
