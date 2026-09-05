"""Halaman admin — Pengaturan Model.

Admin melihat model aktif dan memilih model `.pkl` lain dari daftar yang
sudah tersedia (data tiruan untuk tahap frontend) — aplikasi tidak melatih
atau mengubah parameter model apa pun, hanya menyimpan pilihan ke
`config.json`.
"""

from __future__ import annotations

import streamlit as st

from auth import require_admin
from config import get_model_aktif, set_model_aktif
from data.mock_models import DEFAULT_MODEL_AKTIF, get_info_model, get_model_tersedia

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>⚙️ Pengaturan Model</h1>
        <p>Lihat &amp; ganti model prediksi yang aktif dipakai aplikasi (data tiruan).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

model_list = get_model_tersedia()
nama_model_list = [m.nama_file for m in model_list]

# Slot ini diisi di akhir skrip, supaya kartu "Model Aktif" selalu
# menampilkan nilai terbaru walau baru saja diubah lewat form di bawah.
slot_model_aktif = st.container()

st.markdown("#### Ganti Model Aktif")
_, kolom_form, _ = st.columns([1, 1.6, 1])
with kolom_form:
    with st.container(border=True):
        model_aktif_sekarang = get_model_aktif() or DEFAULT_MODEL_AKTIF
        index_aktif = (
            nama_model_list.index(model_aktif_sekarang) if model_aktif_sekarang in nama_model_list else 0
        )
        nama_terpilih = st.selectbox("Pilih model", options=nama_model_list, index=index_aktif)
        model_terpilih = get_info_model(nama_terpilih)
        if model_terpilih:
            st.caption(f"{model_terpilih.deskripsi} · dilatih {model_terpilih.dilatih_pada}")

        # Slot juga, supaya peringatan "belum disimpan" langsung hilang di run
        # yang sama begitu tombol Simpan ditekan (bukan baru di rerun berikutnya).
        slot_peringatan = st.container()

        if st.button("Simpan Model Aktif", width="stretch"):
            if nama_terpilih == model_aktif_sekarang:
                st.info("Model ini sudah aktif.")
            else:
                set_model_aktif(nama_terpilih)
                st.success(f"Model aktif diubah ke **{nama_terpilih}**.")

        model_aktif_terkini = get_model_aktif() or DEFAULT_MODEL_AKTIF
        if nama_terpilih != model_aktif_terkini:
            with slot_peringatan:
                st.warning("⚠️ Perubahan belum disimpan. Klik **Simpan Model Aktif** untuk menerapkan.")

model_aktif_final = get_model_aktif() or DEFAULT_MODEL_AKTIF
info_aktif = get_info_model(model_aktif_final)
with slot_model_aktif:
    st.markdown("#### Model Aktif Saat Ini")
    with st.container(border=True):
        if info_aktif:
            st.markdown(f"**{info_aktif.nama_file}**")
            st.caption(f"{info_aktif.deskripsi} · dilatih {info_aktif.dilatih_pada}")
        else:
            st.markdown(f"**{model_aktif_final}**")
