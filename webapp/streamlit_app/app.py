"""Entry point aplikasi Streamlit Prediksi Pangan Jogja.

Fase 1: kerangka navigasi + halaman Dashboard Pangan (data tiruan).
Halaman lain ditambahkan pada task-nya masing-masing.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

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

    navigation = st.navigation({"Menu": [dashboard_page, historis_page]})
    navigation.run()


if __name__ == "__main__":
    main()
