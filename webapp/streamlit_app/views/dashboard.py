"""Halaman Dashboard Pangan (publik) — kartu 9 komoditas + detail-nya."""

from __future__ import annotations

import streamlit as st

from data.mock_commodities import get_kategori_list
from data.mock_prices import KartuHarga, get_dashboard_cards
from formatting import format_rupiah, format_waktu_pembaruan, tren_status

_KELAS_TREN_KARTU = {"naik": "ppj-trend-up", "turun": "ppj-trend-down", "tetap": "ppj-trend-flat"}


def _tren_harian(kartu: KartuHarga) -> tuple[str, str]:
    """(kelas_css, label) panah naik/turun/tetap dibanding harga kemarin."""
    status, label = tren_status(kartu.harga_terbaru, kartu.harga_kemarin)
    return _KELAS_TREN_KARTU[status], label


def _gambar_kartu(kartu: KartuHarga) -> None:
    harga_format = format_rupiah(kartu.harga_terbaru)
    kelas_tren, label_tren = _tren_harian(kartu)
    st.markdown(
        f"""
        <div class="ppj-card">
            <div class="ppj-card-head">
                <span class="ppj-card-icon">{kartu.komoditas.ikon}</span>
                <h4>{kartu.komoditas.nama}</h4>
            </div>
            <p class="ppj-price">Rp {harga_format} <span class="ppj-unit">/ {kartu.komoditas.unit}</span></p>
            <p class="{kelas_tren}">{label_tren} dari kemarin</p>
            <p class="ppj-updated">🕒 {format_waktu_pembaruan(kartu.diperbarui_pada)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Lihat Detail", key=f"detail-{kartu.komoditas.slug}", width="stretch"):
        st.session_state["komoditas_dipilih"] = kartu.komoditas.slug
        st.switch_page("views/detail_komoditas.py")


def tampilkan_grid_dashboard() -> None:
    st.markdown(
        """
        <div class="ppj-hero">
            <h1>🌾 Prediksi Pangan Jogja</h1>
            <p>Pantau harga 9 komoditas pangan di Yogyakarta &amp; lihat prediksinya.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kartu_list = get_dashboard_cards()
    kolom_per_baris = 3

    for kunci_kategori, label_kategori in get_kategori_list():
        kelompok = [k for k in kartu_list if k.komoditas.kategori == kunci_kategori]
        if not kelompok:
            continue

        st.markdown(f"#### {label_kategori}")
        for awal in range(0, len(kelompok), kolom_per_baris):
            kolom = st.columns(kolom_per_baris)
            for kolom_slot, kartu in zip(kolom, kelompok[awal : awal + kolom_per_baris]):
                with kolom_slot:
                    with st.container(border=False):
                        _gambar_kartu(kartu)
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)


tampilkan_grid_dashboard()
