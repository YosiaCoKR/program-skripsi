"""Data harga tiruan (stub) untuk tahap frontend.

Menghasilkan deret harga harian 90 hari terakhir per komoditas dengan random
walk yang dibuat deterministik (seed dari slug), supaya nilainya tidak
berubah-ubah tiap Streamlit menjalankan ulang skrip. Modul ini akan diganti
sumbernya dengan pembacaan file `.pkl` riwayat harga pada task backend —
kontrak fungsi (`get_price_history`, `get_dashboard_cards`) dipertahankan
supaya halaman tidak perlu diubah lagi.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from data.mock_commodities import Komoditas, get_komoditas_list

RENTANG_HARI_MAKS = 90

_HARGA_DASAR = {
    "beras-kualitas-bawah-i": 10_650,
    "beras-kualitas-bawah-ii": 10_150,
    "beras-kualitas-medium-i": 12_050,
    "beras-kualitas-medium-ii": 11_300,
    "beras-kualitas-super-i": 13_100,
    "beras-kualitas-super-ii": 12_700,
    "bawang-merah-ukuran-sedang": 34_500,
    "cabai-rawit-hijau": 58_000,
    "cabai-rawit-merah": 71_250,
}

# Jam sejak terakhir diperbarui — beda per komoditas supaya kartu terasa
# nyata (data tidak semuanya diperbarui pada detik yang sama).
_JAM_SEJAK_DIPERBARUI = {
    "beras-kualitas-bawah-i": 2,
    "beras-kualitas-bawah-ii": 2,
    "beras-kualitas-medium-i": 3,
    "beras-kualitas-medium-ii": 3,
    "beras-kualitas-super-i": 4,
    "beras-kualitas-super-ii": 4,
    "bawang-merah-ukuran-sedang": 6,
    "cabai-rawit-hijau": 1,
    "cabai-rawit-merah": 1,
}

_cache_riwayat: dict[str, pd.DataFrame] = {}


@dataclass(frozen=True)
class KartuHarga:
    komoditas: Komoditas
    harga_terbaru: float
    harga_kemarin: float
    diperbarui_pada: datetime


@dataclass(frozen=True)
class HasilPrediksi:
    harga_sekarang: float
    harga_prediksi: float
    persen_perubahan: float


def _seed_dari_slug(slug: str) -> int:
    return zlib.crc32(slug.encode("utf-8"))


def _bangun_riwayat(slug: str, harga_dasar: float, hari: int = RENTANG_HARI_MAKS) -> pd.DataFrame:
    rng = np.random.default_rng(_seed_dari_slug(slug))
    langkah = rng.normal(loc=0, scale=harga_dasar * 0.006, size=hari)
    jalan_acak = np.cumsum(langkah)
    harga = jalan_acak - jalan_acak[-1] + harga_dasar
    harga = np.clip(np.round(harga / 25) * 25, harga_dasar * 0.6, None)

    tanggal_akhir = datetime.now().date()
    tanggal = pd.date_range(end=tanggal_akhir, periods=hari, freq="D")
    return pd.DataFrame({"tanggal": tanggal, "harga": harga})


def get_price_history(slug: str, hari: int = RENTANG_HARI_MAKS) -> pd.DataFrame:
    """Riwayat harga harian (kolom: tanggal, harga) untuk `hari` terakhir."""
    if slug not in _cache_riwayat:
        harga_dasar = _HARGA_DASAR.get(slug, 10_000)
        _cache_riwayat[slug] = _bangun_riwayat(slug, harga_dasar)
    return _cache_riwayat[slug].tail(hari).reset_index(drop=True)


def get_mock_prediction(slug: str, hari_ke_depan: int) -> HasilPrediksi:
    """Prediksi tiruan untuk `hari_ke_depan` hari — pengganti sementara model `.pkl`.

    Melanjutkan random walk yang sama (seed dari slug) supaya konsisten
    antar rerun Streamlit. Diganti pemanggilnya dengan model `.pkl` asli
    pada task backend; bentuk `HasilPrediksi` dipertahankan.
    """
    riwayat = get_price_history(slug, hari=1)
    harga_sekarang = float(riwayat["harga"].iloc[-1])

    harga_dasar = _HARGA_DASAR.get(slug, 10_000)
    rng = np.random.default_rng(_seed_dari_slug(slug) ^ hari_ke_depan)
    langkah = rng.normal(loc=0, scale=harga_dasar * 0.006, size=hari_ke_depan)
    harga_prediksi = harga_sekarang + float(np.sum(langkah))
    harga_prediksi = max(round(harga_prediksi / 25) * 25, harga_dasar * 0.5)

    persen_perubahan = (harga_prediksi - harga_sekarang) / harga_sekarang * 100
    return HasilPrediksi(harga_sekarang, harga_prediksi, persen_perubahan)


def get_dashboard_cards() -> list[KartuHarga]:
    """Harga terbaru + waktu update tiap komoditas, untuk kartu di Dashboard Pangan."""
    sekarang = datetime.now()
    kartu = []
    for komoditas in get_komoditas_list():
        riwayat = get_price_history(komoditas.slug, hari=2)
        harga_terbaru = float(riwayat["harga"].iloc[-1])
        harga_kemarin = float(riwayat["harga"].iloc[0]) if len(riwayat) > 1 else harga_terbaru
        jam_lalu = _JAM_SEJAK_DIPERBARUI.get(komoditas.slug, 2)
        diperbarui_pada = sekarang - timedelta(hours=jam_lalu)
        kartu.append(KartuHarga(komoditas, harga_terbaru, harga_kemarin, diperbarui_pada))
    return kartu
