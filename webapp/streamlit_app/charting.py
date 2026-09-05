"""Grafik harga (Plotly) yang dipakai bersama — Detail Komoditas & Data Historis.

Prinsip yang dipegang: marka tipis, grid hairline redup, label nilai hanya di
titik yang penting (akhir historis & titik prediksi — bukan tiap titik),
tooltip gelap yang menyatu dengan tema aplikasi. Sumbu-Y dibiarkan mengikuti
rentang data asli (tidak dipaksa dari nol) supaya fluktuasi harga tetap
terbaca — komoditas Rp 50–70rb tidak jadi terlihat rata seperti garis lurus.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from formatting import format_rupiah

_WARNA_HISTORIS = "#199e70"
_WARNA_PREDIKSI = "#c98500"
_WARNA_GRID = "rgba(255, 255, 255, 0.08)"
_WARNA_SUMBU = "rgba(255, 255, 255, 0.18)"
_WARNA_TEKS_MUTED = "rgba(230, 230, 224, 0.65)"
_WARNA_TEKS_PRIMER = "rgba(255, 255, 255, 0.95)"
_CINCIN_PERMUKAAN = "#0d0f0e"
# Latar chart di-set TETAP gelap (bukan transparan/ikut tema Streamlit) —
# kalau dibiarkan transparan, chart ini jadi putih kosong tanpa gridline
# terbaca saat browser/sistem pengguna memakai tema terang (semua warna
# grid/teks di atas dirancang untuk latar gelap, jadi nyaris tak terlihat
# di atas latar putih). Dengan latar tetap gelap, chart selalu konsisten
# terlepas dari preferensi tema perangkat pengguna.
_WARNA_LATAR = "#12181a"


def gambar_grafik_harga(
    riwayat: pd.DataFrame,
    unit: str,
    *,
    height: int = 380,
    prediksi_tanggal: Optional[date] = None,
    prediksi_harga_sekarang: Optional[float] = None,
    prediksi_harga: Optional[float] = None,
    prediksi_label: Optional[str] = None,
    prediksi_persen: Optional[float] = None,
) -> None:
    """Gambar grafik garis harga historis, dengan garis prediksi opsional."""
    ada_prediksi = prediksi_tanggal is not None and prediksi_harga is not None

    tanggal_akhir = riwayat["tanggal"].iloc[-1]
    harga_akhir = float(riwayat["harga"].iloc[-1])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=riwayat["tanggal"],
            y=riwayat["harga"],
            mode="lines",
            line=dict(color=_WARNA_HISTORIS, width=2),
            name="Harga historis",
            hovertemplate="%{x|%d %b %Y}<br>Rp %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[tanggal_akhir],
            y=[harga_akhir],
            mode="markers",
            marker=dict(size=8, color=_WARNA_HISTORIS, line=dict(width=2, color=_CINCIN_PERMUKAAN)),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    # Label harga terkini hanya ditampilkan kalau TIDAK ada prediksi — begitu
    # prediksi aktif, titik historis & titik prediksi bisa berdekatan (rentang
    # 1/7 hari), dan harga terkini sudah tertulis besar di kartu di atas grafik,
    # jadi melabeli titik ini lagi cuma bikin dua label bertumpuk (lihat
    # marks-and-anatomy: label yang bentrok jangan ditumpuk).
    if not ada_prediksi:
        fig.add_annotation(
            x=tanggal_akhir,
            y=harga_akhir,
            text=f"Rp {format_rupiah(harga_akhir)}",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            xshift=10,
            yshift=6,
            font=dict(color=_WARNA_TEKS_PRIMER, size=12),
        )

    if ada_prediksi:
        fig.add_trace(
            go.Scatter(
                x=[tanggal_akhir, prediksi_tanggal],
                y=[prediksi_harga_sekarang, prediksi_harga],
                mode="lines+markers",
                line=dict(color=_WARNA_PREDIKSI, width=2, dash="dash"),
                marker=dict(
                    size=8,
                    symbol="diamond",
                    color=_WARNA_PREDIKSI,
                    line=dict(width=2, color=_CINCIN_PERMUKAAN),
                ),
                name=prediksi_label or "Prediksi",
                hovertemplate="%{x|%d %b %Y}<br>Prediksi: Rp %{y:,.0f}<extra></extra>",
            )
        )
        label_prediksi = f"Rp {format_rupiah(prediksi_harga)}"
        if prediksi_persen is not None:
            label_prediksi += f"  ({prediksi_persen:+.1f}%)"
        fig.add_annotation(
            x=prediksi_tanggal,
            y=prediksi_harga,
            text=label_prediksi,
            showarrow=False,
            xanchor="left",
            yanchor="top",
            xshift=10,
            yshift=-6,
            font=dict(color=_WARNA_TEKS_PRIMER, size=12),
        )

    fig.update_layout(
        margin=dict(l=90, r=110, t=10, b=40),
        height=height,
        xaxis_title="Tanggal",
        yaxis_title=f"Harga (Rp/{unit})",
        template="plotly_white",
        paper_bgcolor=_WARNA_LATAR,
        plot_bgcolor=_WARNA_LATAR,
        hovermode="x unified",
        showlegend=ada_prediksi,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=_WARNA_TEKS_MUTED, size=12),
        ),
        separators=",.",
        hoverlabel=dict(
            bgcolor="#181c1a",
            bordercolor="rgba(255,255,255,0.15)",
            font=dict(color=_WARNA_TEKS_PRIMER, size=13),
        ),
        font=dict(color=_WARNA_TEKS_MUTED),
    )
    fig.update_xaxes(
        tickformat="%d %b",
        showgrid=False,
        color=_WARNA_TEKS_MUTED,
        linecolor=_WARNA_SUMBU,
        showline=True,
    )
    fig.update_yaxes(
        tickformat=",.0f",
        showgrid=True,
        gridcolor=_WARNA_GRID,
        gridwidth=1,
        zeroline=False,
        color=_WARNA_TEKS_MUTED,
        rangemode="normal",
    )
    st.plotly_chart(fig, width="stretch", theme=None)
