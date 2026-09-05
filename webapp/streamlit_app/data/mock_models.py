"""Daftar tiruan model prediksi `.pkl` yang tersedia untuk dipilih admin.

Aplikasi tidak melatih model — hanya memuat file yang sudah jadi dan
tersedia (sesuai PRD). Untuk tahap frontend, daftar ini masih data tiruan;
diganti dengan pemindaian folder model sungguhan pada task backend.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MODEL_AKTIF = "ga_lightgbm_v2.pkl"


@dataclass(frozen=True)
class InfoModel:
    nama_file: str
    deskripsi: str
    dilatih_pada: str
    # Faktor tiruan yang membedakan "karakter" tiap model pada prediksi mock —
    # 1.0 = baseline, lebih rendah = lebih stabil (hasil tuning), lebih tinggi
    # = lebih liar (kandidat belum divalidasi). Diganti dengan model `.pkl`
    # sungguhan pada task berikutnya; field ini cuma supaya pilihan admin di
    # Pengaturan Model benar-benar terasa efeknya di prediksi publik.
    faktor_volatilitas: float = 1.0


def get_model_tersedia() -> list[InfoModel]:
    return [
        InfoModel(
            "ga_lightgbm_v1.pkl",
            "GA-LightGBM awal — 27 model per komoditas x horizon",
            "15 Agu 2026",
            faktor_volatilitas=1.0,
        ),
        InfoModel(
            "ga_lightgbm_v2.pkl",
            "GA-LightGBM hasil tuning ulang (generasi GA lebih banyak)",
            "28 Agu 2026",
            faktor_volatilitas=0.7,
        ),
        InfoModel(
            "ga_lightgbm_v3_candidate.pkl",
            "Kandidat baru — belum divalidasi penuh",
            "02 Sep 2026",
            faktor_volatilitas=1.4,
        ),
    ]


def get_info_model(nama_file: str) -> InfoModel | None:
    return next((m for m in get_model_tersedia() if m.nama_file == nama_file), None)
