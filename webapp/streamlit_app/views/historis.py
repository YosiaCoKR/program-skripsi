"""Halaman Data Historis — tren harga 30/60/90 hari untuk komoditas pilihan."""

from __future__ import annotations

import streamlit as st

from charting import gambar_grafik_harga
from data.mock_commodities import get_komoditas_list
from data.mock_prices import get_price_history

RENTANG_HISTORIS = {"30 Hari": 30, "60 Hari": 60, "90 Hari": 90}


def _gambar_chart(slug: str, unit: str, hari: int) -> None:
    riwayat = get_price_history(slug, hari=hari)

    if riwayat.empty:
        st.markdown(
            '<div class="ppj-placeholder">Data historis belum tersedia untuk komoditas '
            "dan rentang waktu ini.</div>",
            unsafe_allow_html=True,
        )
        return

    gambar_grafik_harga(riwayat, unit, height=420)


st.markdown(
    """
    <div class="ppj-hero">
        <h1>📈 Data Historis</h1>
        <p>Tren harga 30 / 60 / 90 hari ke belakang (data tiruan).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

komoditas_list = get_komoditas_list()
kolom_komoditas, kolom_rentang = st.columns([2, 1], gap="medium")

with kolom_komoditas:
    nama_terpilih = st.selectbox("Komoditas", options=[k.nama for k in komoditas_list])

with kolom_rentang:
    label_rentang = st.segmented_control(
        "Rentang waktu",
        options=list(RENTANG_HISTORIS.keys()),
        default="30 Hari",
    )

komoditas_terpilih = next(k for k in komoditas_list if k.nama == nama_terpilih)
label_rentang = label_rentang or "30 Hari"
hari_terpilih = RENTANG_HISTORIS[label_rentang]

st.markdown(f"#### Tren Harga — {komoditas_terpilih.nama} ({label_rentang})")
_gambar_chart(komoditas_terpilih.slug, komoditas_terpilih.unit, hari_terpilih)
