"""Gerbang akses admin — satu kata sandi dari konfigurasi aplikasi.

Tidak ada tabel `users` maupun akun terdaftar (sesuai PRD): status masuk
admin cukup disimpan di `st.session_state` untuk sesi tab yang sedang
berjalan. Setiap login/logout dicatat ke `db.admin_login_logs` (audit
ringan, tanpa identitas selain peran "admin").

Kata sandi dibaca dari environment variable `ADMIN_PASSWORD`. Untuk
pengembangan lokal, salin `.env.example` jadi `.env` (sudah di-gitignore)
dan isi nilainya — `load_dotenv()` di bawah memuatnya otomatis tanpa perlu
export manual di shell. Kalau `.env`/env var tidak ada, dipakai nilai
default dev supaya halaman tetap bisa dicoba.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from db import catat_aktivitas_admin

load_dotenv(Path(__file__).parent / ".env")

_ADMIN_PASSWORD_DEFAULT = "admin123"  # dev/demo — WAJIB diganti via ADMIN_PASSWORD di produksi
_SESSION_KEY = "admin_masuk"
_SESI_ID_KEY = "admin_sesi_id"


def kata_sandi_admin() -> str:
    return os.environ.get("ADMIN_PASSWORD", _ADMIN_PASSWORD_DEFAULT)


def admin_sudah_masuk() -> bool:
    return bool(st.session_state.get(_SESSION_KEY, False))


def masuk_sebagai_admin() -> None:
    st.session_state[_SESSION_KEY] = True


def _sesi_id() -> str:
    """Penanda sesi tab admin (bukan identitas pengguna) — dipakai di log."""
    if _SESI_ID_KEY not in st.session_state:
        st.session_state[_SESI_ID_KEY] = uuid.uuid4().hex[:12]
    return st.session_state[_SESI_ID_KEY]


def login(kata_sandi: str) -> bool:
    """"Endpoint" login admin — verifikasi kata sandi & aktifkan sesi bila cocok.

    Aplikasi ini adalah Streamlit monolith tanpa server API terpisah (sesuai
    arsitektur PRD): "endpoint" di sini adalah fungsi Python yang dipanggil
    langsung oleh halaman UI, bukan rute HTTP.
    """
    if kata_sandi == kata_sandi_admin():
        masuk_sebagai_admin()
        catat_aktivitas_admin("login", _sesi_id())
        return True
    return False


def keluar_dari_admin() -> None:
    if admin_sudah_masuk():
        catat_aktivitas_admin("logout", _sesi_id())
    st.session_state.pop(_SESSION_KEY, None)


def require_admin() -> None:
    """Panggil di awal skrip halaman admin selain login (Input Harga, Pengaturan
    Model, dst). Menghentikan render halaman kalau sesi admin belum aktif,
    supaya rute admin tidak bisa dilihat isinya lewat akses URL langsung
    tanpa login.
    """
    if not admin_sudah_masuk():
        st.warning(
            "Anda harus masuk sebagai admin terlebih dahulu. "
            "Buka halaman **Panel Admin** di menu untuk masuk."
        )
        st.stop()
