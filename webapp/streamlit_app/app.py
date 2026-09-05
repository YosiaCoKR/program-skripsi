"""Entry point aplikasi Streamlit Prediksi Pangan Jogja.

Fase 1: kerangka navigasi + halaman Dashboard Pangan (data tiruan).
Halaman lain ditambahkan pada task-nya masing-masing.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from auth import admin_sudah_masuk

APP_DIR = Path(__file__).parent


def load_custom_css() -> None:
    css_path = APP_DIR / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="Prediksi Pangan Jogja",
        page_icon="🌾",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    load_custom_css()

    dashboard_page = st.Page(
        "views/dashboard.py",
        title="Dashboard Pangan",
        icon="🏠",
        default=True,
    )
    historis_page = st.Page(
        "views/historis.py",
        title="Data Historis",
        icon="📈",
    )
    detail_komoditas_page = st.Page(
        "views/detail_komoditas.py",
        title="Detail Komoditas",
        icon="🔍",
        url_path="detail-komoditas",
        visibility="hidden",
    )
    admin_login_page = st.Page(
        "views/admin_login.py",
        title="Panel Admin",
        icon="🔒",
    )
    # Halaman kerja admin baru muncul di sidebar SETELAH login — sebelum itu,
    # cuma "Panel Admin" (login) yang terlihat di grup Admin. Ini bukan
    # pengganti proteksi `auth.require_admin()` di tiap halaman (URL langsung
    # masih diblokir), cuma supaya navbar terasa benar-benar terpisah antara
    # publik dan admin yang sudah masuk.
    visibilitas_admin = "visible" if admin_sudah_masuk() else "hidden"
    admin_input_harga_page = st.Page(
        "views/admin_input_harga.py",
        title="Input Harga Terbaru",
        icon="✏️",
        visibility=visibilitas_admin,
    )
    admin_model_settings_page = st.Page(
        "views/admin_model_settings.py",
        title="Pengaturan Model",
        icon="⚙️",
        visibility=visibilitas_admin,
    )

    navigation = st.navigation(
        {
            "Menu": [dashboard_page, historis_page, detail_komoditas_page],
            "Admin": [admin_login_page, admin_input_harga_page, admin_model_settings_page],
        }
    )
    navigation.run()


if __name__ == "__main__":
    main()
