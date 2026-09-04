"""Tampilan detail komoditas: grafik harga historis + kontrol prediksi.

Angka hasil prediksi & persentase kenaikan 30 hari ditambahkan pada task
berikutnya — di sini baru grafik + pemilihan rentang (1/7/30 hari).
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from data.mock_commodities import get_komoditas_by_slug
from data.mock_prices import get_mock_prediction, get_price_history

RENTANG_PREDIKSI = {"1 Hari": 1, "7 Hari": 7, "30 Hari": 30}


def _gambar_chart(slug: str, unit: str) -> None:
    riwayat = get_price_history(slug, hari=90)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=riwayat["tanggal"],
            y=riwayat["harga"],
            mode="lines",
            line=dict(color="#1f8a4c", width=2),
            fill="tozeroy",
            fillcolor="rgba(31, 138, 76, 0.08)",
            name="Harga",
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=380,
        yaxis_title=f"Harga (Rp/{unit})",
        template="plotly_white",
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


def tampilkan_detail(slug: str) -> None:
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        st.error("Komoditas tidak ditemukan.")
        return

    if st.button("← Kembali ke Dashboard"):
        st.session_state.pop("komoditas_dipilih", None)
        st.rerun()

    st.markdown(
        f"""
        <div class="ppj-hero">
            <h1>{komoditas.nama}</h1>
            <p>Grafik pergerakan harga 90 hari terakhir (data tiruan).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kolom_chart, kolom_prediksi = st.columns([3, 1])

    with kolom_chart:
        _gambar_chart(slug, komoditas.unit)

    with kolom_prediksi:
        st.markdown("**Prediksi Harga**")
        label_rentang = st.selectbox(
            "Rentang prediksi",
            options=list(RENTANG_PREDIKSI.keys()),
            index=1,
            key=f"rentang-prediksi-{slug}",
            label_visibility="collapsed",
        )
        if st.button("Prediksi", key=f"tombol-prediksi-{slug}", width="stretch"):
            st.session_state[f"prediksi-aktif-{slug}"] = RENTANG_PREDIKSI[label_rentang]

        rentang_terpilih = st.session_state.get(f"prediksi-aktif-{slug}")
        if rentang_terpilih:
            hasil = get_mock_prediction(slug, rentang_terpilih)
            harga_format = f"{hasil.harga_prediksi:,.0f}".replace(",", ".")
            delta = None
            if rentang_terpilih == 30:
                delta = f"{hasil.persen_perubahan:+.2f}% dalam 30 hari"
            st.metric(
                label=f"Prediksi {rentang_terpilih} hari lagi",
                value=f"Rp {harga_format}",
                delta=delta,
            )
