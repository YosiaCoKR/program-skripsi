"""Konfigurasi global aplikasi PANGANIA."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Lokasi direktori
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
WEBAPP_DIR = BACKEND_DIR.parent
RESEARCH_DIR = WEBAPP_DIR / "research"  # notebook, dataset, dan artefak penelitian

ARTIFACT_DIR = BACKEND_DIR / "artifacts"
MODEL_DIR = ARTIFACT_DIR / "models"
DATA_DIR = BACKEND_DIR / "data"

for _d in (ARTIFACT_DIR, MODEL_DIR, DATA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Artefak hasil penelitian (step 4 & 5 di workflow-program.md).
# Dimuat apa adanya — aplikasi tidak pernah me-refit atau menulis ulang.
TREND_MODELS_PATH = RESEARCH_DIR / "trend_models.pkl"
FEATURE_TRANSFORMERS_PATH = RESEARCH_DIR / "features_transformers.pkl"
STL_RESULTS_PATH = RESEARCH_DIR / "stl_results.pkl"
RAW_DATASET_PATH = RESEARCH_DIR / "DATASET-BERAS.csv"

DATABASE_URL = os.environ.get(
    "PANGANIA_DATABASE_URL", f"sqlite:///{DATA_DIR / 'pangania.db'}"
)

# ---------------------------------------------------------------------------
# Keamanan
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "PANGANIA_SECRET_KEY", "pangania-dev-secret-ganti-di-produksi"
)
SESSION_COOKIE = "pangania_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 jam
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

DEFAULT_ADMIN_EMAIL = os.environ.get("PANGANIA_ADMIN_EMAIL", "admin@pangania.id")
DEFAULT_ADMIN_PASSWORD = os.environ.get("PANGANIA_ADMIN_PASSWORD", "pangania2026")
DEFAULT_ADMIN_NAME = os.environ.get("PANGANIA_ADMIN_NAME", "Yosia Sipahutar")

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

# PENTING — konversi skala.
# Dataset penelitian menyimpan harga dalam satuan RIBU rupiah (mis. 10.4 = Rp 10.400)
# karena `pd.read_csv` membaca "10.400" sebagai desimal 10.4. Seluruh artefak model
# (trend_models, MSTL, transformer) dilatih pada skala tersebut.
#
# Basis data dan antarmuka menyimpan/menampilkan harga dalam RUPIAH PENUH supaya
# admin mengetik angka yang wajar. Konversi HANYA terjadi di lapisan ML, lewat
# konstanta ini. Jangan pernah melakukan konversi di tempat lain.
MODEL_PRICE_SCALE = 1000.0

# Tanggal awal dataset penelitian. `time_index` yang dipakai trend_models adalah
# jumlah hari sejak tanggal ini (notebook: np.arange(len(df_cleaned)) pada indeks
# harian yang kontinu).
SERIES_START_DATE = "2021-01-04"

HORIZONS = (1, 7, 30)

HORIZON_LABELS = {
    1: "Harian",
    7: "Mingguan",
    30: "Bulanan",
}

HORIZON_DESCRIPTIONS = {
    1: "Prediksi harga 1 hari ke depan (H+1)",
    7: "Prediksi harga 7 hari ke depan (H+7)",
    30: "Prediksi harga 30 hari ke depan (H+30)",
}

# Ambang peringatan admin untuk trend extrapolation drift (PRD §7.6 poin 1).
DRIFT_WARNING_DAYS = 90
DRIFT_CRITICAL_DAYS = 180

# Validasi input harga (PRD fitur #8): lonjakan di atas nilai ini memicu
# konfirmasi, bukan penolakan — lonjakan cabai memang wajar terjadi.
OUTLIER_PCT_THRESHOLD = 20.0

# Master 9 komoditas.
#
# `color_slot` mengunci warna seri grafik ke ENTITAS, bukan ke urutan tampil
# (PRD §7.4), sehingga menyaring komoditas tidak pernah memindahkan warna
# komoditas yang tersisa.
#
# Slot dibuat unik lintas seluruh 9 komoditas — bukan per keluarga — karena
# halaman Eksplorasi Data Historis boleh memilih komoditas dari keluarga
# berbeda; kalau slot hanya unik di dalam keluarga, dua komoditas lintas
# keluarga bisa tampil dengan warna identik di grafik yang sama.
#
# Palet kategorikal tervalidasi punya 8 slot, sedangkan komoditas ada 9. Slot 9
# adalah perluasan yang didokumentasikan (lihat frontend `palette.ts`). Ini aman
# karena PRD membatasi tampilan maksimal 6 seri untuk grafik garis dan 3 seri
# untuk explorer — kesembilan warna tidak pernah tampil serentak.
#
# Enam varietas beras sengaja mendapat slot 1-6 berurutan karena merekalah
# kelompok yang paling mungkin dibandingkan dalam satu grafik.
COMMODITIES: list[dict] = [
    {
        "code": "beras-bawah-1",
        "name": "Beras Kualitas Bawah I",
        "family": "Beras",
        "color_slot": 1,
    },
    {
        "code": "beras-bawah-2",
        "name": "Beras Kualitas Bawah II",
        "family": "Beras",
        "color_slot": 2,
    },
    {
        "code": "beras-medium-1",
        "name": "Beras Kualitas Medium I",
        "family": "Beras",
        "color_slot": 3,
    },
    {
        "code": "beras-medium-2",
        "name": "Beras Kualitas Medium II",
        "family": "Beras",
        "color_slot": 4,
    },
    {
        "code": "beras-super-1",
        "name": "Beras Kualitas Super I",
        "family": "Beras",
        "color_slot": 5,
    },
    {
        "code": "beras-super-2",
        "name": "Beras Kualitas Super II",
        "family": "Beras",
        "color_slot": 6,
    },
    {
        "code": "bawang-merah-sedang",
        "name": "Bawang Merah Ukuran Sedang",
        "family": "Bawang Merah",
        "color_slot": 7,
    },
    {
        "code": "cabai-rawit-hijau",
        "name": "Cabai Rawit Hijau",
        "family": "Cabai Rawit",
        "color_slot": 8,
    },
    {
        "code": "cabai-rawit-merah",
        "name": "Cabai Rawit Merah",
        "family": "Cabai Rawit",
        "color_slot": 9,
    },
]

# Warna tingkat keluarga (PRD §7.4) — dipakai untuk pengelompokan dashboard dan
# perbandingan lintas keluarga, terpisah dari `color_slot` per komoditas.
FAMILY_COLOR_SLOT = {
    "Beras": 1,
    "Bawang Merah": 2,
    "Cabai Rawit": 3,
}

# Ambang batas EWS bawaan (dapat diubah admin — PRD requirement).
DEFAULT_EWS_THRESHOLDS = {
    "threshold_waspada": 1.0,
    "threshold_warning": 1.5,
    "threshold_kritis": 2.0,
}
