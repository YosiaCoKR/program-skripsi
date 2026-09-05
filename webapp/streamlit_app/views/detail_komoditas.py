"""Tampilan detail komoditas: hero info harga, grafik historis + garis prediksi.

Anotasi ambang batas & pop-up peringatan dini ditambahkan pada task
tersendiri — di sini fokus pada grafik (riwayat + garis prediksi) dan
panel kontrol prediksi.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from charting import gambar_grafik_harga
from data.mock_commodities import get_komoditas_by_slug
from data.mock_prices import HasilPrediksi, get_kartu_harga, get_mock_prediction, get_price_history
from formatting import format_rupiah, format_waktu_pembaruan, tren_status

RENTANG_PREDIKSI = {"1 Hari": 1, "7 Hari": 7, "30 Hari": 30}

_KELAS_TREN_HERO = {
    "naik": "ppj-hero-trend-up",
    "turun": "ppj-hero-trend-down",
    "tetap": "ppj-hero-trend-flat",
}


def _gambar_chart(
    slug: str,
    unit: str,
    hari_ke_depan: int | None = None,
    hasil: HasilPrediksi | None = None,
) -> None:
    riwayat = get_price_history(slug, hari=90)
    ada_prediksi = hari_ke_depan is not None and hasil is not None

    if not ada_prediksi:
        gambar_grafik_harga(riwayat, unit)
        return

    tanggal_prediksi = riwayat["tanggal"].iloc[-1] + pd.Timedelta(days=hari_ke_depan)
    persen = hasil.persen_perubahan if hari_ke_depan == 30 else None
    gambar_grafik_harga(
        riwayat,
        unit,
        prediksi_tanggal=tanggal_prediksi,
        prediksi_harga_sekarang=hasil.harga_sekarang,
        prediksi_harga=hasil.harga_prediksi,
        prediksi_label=f"Prediksi {hari_ke_depan} hari",
        prediksi_persen=persen,
    )


def _gambar_hero(slug: str) -> None:
    kartu = get_kartu_harga(slug)
    if kartu is None:
        return

    komoditas = kartu.komoditas
    status, label_tren = tren_status(kartu.harga_terbaru, kartu.harga_kemarin)
    kelas_tren = _KELAS_TREN_HERO[status]

    st.markdown(
        f"""
        <div class="ppj-hero ppj-hero-detail">
            <div class="ppj-hero-detail-head">
                <span class="ppj-hero-detail-icon">{komoditas.ikon}</span>
                <div>
                    <h1>{komoditas.nama}</h1>
                    <p>Grafik pergerakan harga 90 hari terakhir (data tiruan).</p>
                </div>
            </div>
            <div class="ppj-hero-detail-price">
                <span class="ppj-hero-price-value">Rp {format_rupiah(kartu.harga_terbaru)}</span>
                <span class="ppj-hero-unit">/ {komoditas.unit}</span>
                <span class="{kelas_tren}">{label_tren}</span>
                <span class="ppj-hero-updated">🕒 {format_waktu_pembaruan(kartu.diperbarui_pada)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tampilkan_detail(slug: str) -> None:
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        st.error("Komoditas tidak ditemukan.")
        return

    if st.button("← Kembali ke Dashboard"):
        st.session_state.pop("komoditas_dipilih", None)
        st.switch_page("views/dashboard.py")

    _gambar_hero(slug)

    rentang_terpilih = st.session_state.get(f"prediksi-aktif-{slug}")
    hasil = get_mock_prediction(slug, rentang_terpilih) if rentang_terpilih else None

    kolom_chart, kolom_prediksi = st.columns([3, 1], gap="medium")

    with kolom_chart:
        st.markdown("#### Grafik Harga")
        _gambar_chart(slug, komoditas.unit, rentang_terpilih, hasil)

    with kolom_prediksi:
        st.markdown("#### Prediksi Harga")
        with st.container(border=True):
            label_rentang = st.segmented_control(
                "Rentang prediksi",
                options=list(RENTANG_PREDIKSI.keys()),
                default="7 Hari",
                key=f"rentang-prediksi-{slug}",
                label_visibility="collapsed",
            )
            if st.button(
                "Prediksi",
                key=f"tombol-prediksi-{slug}",
                width="stretch",
                disabled=label_rentang is None,
            ):
                st.session_state[f"prediksi-aktif-{slug}"] = RENTANG_PREDIKSI[label_rentang]
                st.rerun()

            if hasil:
                delta = None
                if rentang_terpilih == 30:
                    delta = f"{hasil.persen_perubahan:+.2f}% dalam 30 hari"
                st.metric(
                    label=f"Prediksi {rentang_terpilih} hari lagi",
                    value=f"Rp {format_rupiah(hasil.harga_prediksi)}",
                    delta=delta,
                )
                st.caption(f"Dihitung dengan model **{hasil.model_dipakai}**.")
            else:
                st.caption("Pilih rentang lalu klik **Prediksi** untuk melihat hasilnya.")


_slug_terpilih = st.session_state.get("komoditas_dipilih")
if _slug_terpilih:
    tampilkan_detail(_slug_terpilih)
else:
    st.warning("Komoditas belum dipilih.")
    if st.button("← Kembali ke Dashboard"):
        st.switch_page("views/dashboard.py")
