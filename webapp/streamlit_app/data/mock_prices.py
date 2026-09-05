"""Data harga historis — dasar tiruan (random walk), edit admin persisten ke `.pkl`.

Riwayat dasar tiap komoditas masih dibangkitkan sebagai random walk
deterministik (seed dari slug) karena file `.pkl` riwayat harga sungguhan
adalah keluaran pipeline model milik pengguna, di luar cakupan proyek ini.
Namun begitu admin menyimpan harga lewat halaman Input Harga Terbaru,
perubahan itu **sungguhan** ditulis ke `harga_historis.pkl` di sebelah modul
ini dan dimuat balik saat aplikasi start — bukan lagi sekadar cache memori
yang hilang setelah proses berhenti. Kontrak fungsi (`get_price_history`,
`get_dashboard_cards`) dipertahankan supaya halaman tidak perlu diubah lagi.
"""

from __future__ import annotations

import pickle
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import get_model_aktif
from data.mock_commodities import Komoditas, get_komoditas_by_slug, get_komoditas_list
from data.mock_models import DEFAULT_MODEL_AKTIF, get_info_model

RENTANG_HARI_MAKS = 90
_PKL_PATH = Path(__file__).parent / "harga_historis.pkl"

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


def _muat_riwayat_dari_pkl() -> None:
    """Muat harga hasil input admin sebelumnya (kalau ada) saat modul di-import."""
    if _PKL_PATH.exists():
        with open(_PKL_PATH, "rb") as berkas:
            _cache_riwayat.update(pickle.load(berkas))


def _simpan_riwayat_ke_pkl() -> None:
    """Tulis seluruh cache riwayat ke `.pkl` — dipanggil tiap admin menyimpan harga."""
    with open(_PKL_PATH, "wb") as berkas:
        pickle.dump(_cache_riwayat, berkas)


_muat_riwayat_dari_pkl()


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
    model_dipakai: str


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

    Memakai model aktif yang dipilih admin di Pengaturan Model: tiap model
    tiruan punya "karakter" (`faktor_volatilitas`) berbeda, jadi mengganti
    model aktif benar-benar mengubah hasil prediksi publik, bukan cuma
    tersimpan di config tanpa efek. Melanjutkan random walk yang sama (seed
    dari slug) supaya konsisten antar rerun Streamlit untuk model yang sama.
    Diganti pemanggilnya dengan model `.pkl` asli pada task selanjutnya.
    """
    riwayat = get_price_history(slug, hari=1)
    harga_sekarang = float(riwayat["harga"].iloc[-1])

    nama_model_aktif = get_model_aktif() or DEFAULT_MODEL_AKTIF
    info_model = get_info_model(nama_model_aktif)
    faktor_volatilitas = info_model.faktor_volatilitas if info_model else 1.0

    harga_dasar = _HARGA_DASAR.get(slug, 10_000)
    rng = np.random.default_rng(_seed_dari_slug(slug) ^ hari_ke_depan)
    langkah = rng.normal(loc=0, scale=harga_dasar * 0.006 * faktor_volatilitas, size=hari_ke_depan)
    harga_prediksi = harga_sekarang + float(np.sum(langkah))
    harga_prediksi = max(round(harga_prediksi / 25) * 25, harga_dasar * 0.5)

    persen_perubahan = (harga_prediksi - harga_sekarang) / harga_sekarang * 100
    return HasilPrediksi(harga_sekarang, harga_prediksi, persen_perubahan, nama_model_aktif)


def tambah_harga_baru(slug: str, tanggal, harga: float) -> None:
    """Tambah/perbarui satu titik harga untuk admin — di-append ke `.pkl` sungguhan.

    Efeknya langsung terlihat: dashboard, detail, dan data historis membaca
    dari cache riwayat yang sama, dan hasilnya sekarang ditulis ke
    `harga_historis.pkl` supaya bertahan setelah aplikasi di-restart.
    """
    if slug not in _cache_riwayat:
        harga_dasar = _HARGA_DASAR.get(slug, 10_000)
        _cache_riwayat[slug] = _bangun_riwayat(slug, harga_dasar)

    df = _cache_riwayat[slug]
    tanggal_ts = pd.Timestamp(tanggal)

    if (df["tanggal"] == tanggal_ts).any():
        df.loc[df["tanggal"] == tanggal_ts, "harga"] = harga
    else:
        baris_baru = pd.DataFrame({"tanggal": [tanggal_ts], "harga": [harga]})
        df = pd.concat([df, baris_baru], ignore_index=True)

    _cache_riwayat[slug] = df.sort_values("tanggal").reset_index(drop=True)
    _simpan_riwayat_ke_pkl()


def get_kartu_harga(slug: str) -> KartuHarga | None:
    """Harga terbaru + waktu update untuk satu komoditas (dipakai kartu & hero detail)."""
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        return None

    riwayat = get_price_history(slug, hari=2)
    harga_terbaru = float(riwayat["harga"].iloc[-1])
    harga_kemarin = float(riwayat["harga"].iloc[0]) if len(riwayat) > 1 else harga_terbaru
    jam_lalu = _JAM_SEJAK_DIPERBARUI.get(slug, 2)
    diperbarui_pada = datetime.now() - timedelta(hours=jam_lalu)
    return KartuHarga(komoditas, harga_terbaru, harga_kemarin, diperbarui_pada)


def get_dashboard_cards() -> list[KartuHarga]:
    """Harga terbaru + waktu update tiap komoditas, untuk kartu di Dashboard Pangan."""
    kartu = (get_kartu_harga(k.slug) for k in get_komoditas_list())
    return [k for k in kartu if k is not None]
