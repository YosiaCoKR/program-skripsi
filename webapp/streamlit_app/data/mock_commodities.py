"""Daftar statis 9 komoditas pangan.

Ini adalah konfigurasi tetap (nama, slug, unit, kategori, ikon) — bukan data
harga. Data harga & riwayatnya (tiruan untuk tahap frontend, nanti dibaca
dari `.pkl` sungguhan pada task backend) ada di `data.mock_prices`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Komoditas:
    slug: str
    nama: str
    unit: str
    kategori: str
    ikon: str


def get_komoditas_list() -> list[Komoditas]:
    """Mengembalikan 9 komoditas pangan sesuai dataset riset (DATASET-BERAS.csv).

    Dikelompokkan jadi 2 kategori (beras & bumbu dapur) supaya dashboard
    lebih mudah dipindai.
    """
    return [
        Komoditas("beras-kualitas-bawah-i", "Beras Kualitas Bawah I", "kg", "beras", "🌾"),
        Komoditas("beras-kualitas-bawah-ii", "Beras Kualitas Bawah II", "kg", "beras", "🌾"),
        Komoditas("beras-kualitas-medium-i", "Beras Kualitas Medium I", "kg", "beras", "🌾"),
        Komoditas("beras-kualitas-medium-ii", "Beras Kualitas Medium II", "kg", "beras", "🌾"),
        Komoditas("beras-kualitas-super-i", "Beras Kualitas Super I", "kg", "beras", "🌾"),
        Komoditas("beras-kualitas-super-ii", "Beras Kualitas Super II", "kg", "beras", "🌾"),
        Komoditas("bawang-merah-ukuran-sedang", "Bawang Merah Ukuran Sedang", "kg", "bumbu", "🧅"),
        Komoditas("cabai-rawit-hijau", "Cabai Rawit Hijau", "kg", "bumbu", "🌶️"),
        Komoditas("cabai-rawit-merah", "Cabai Rawit Merah", "kg", "bumbu", "🌶️"),
    ]


def get_komoditas_by_slug(slug: str) -> Komoditas | None:
    return next((k for k in get_komoditas_list() if k.slug == slug), None)


def get_kategori_list() -> list[tuple[str, str]]:
    """Urutan kategori untuk pengelompokan tampilan: (kunci, label)."""
    return [("beras", "🌾 Beras"), ("bumbu", "🧅 Bumbu Dapur")]
