"""Pembentukan fitur memakai transformer hasil training.

Modul ini TIDAK menulis ulang logika `shift()`/`rolling()`. Ia memanggil objek
`LagFeatures` dan `WindowFeatures` yang sama persis dengan yang di-`fit()` saat
training (PRD requirement "Konsistensi pipeline"), sehingga risiko perbedaan
logika antara training dan produksi hilang secara struktural.

KENDALA YANG DITANGANI DI SINI
------------------------------
Di notebook, transformer di-`fit()` di atas DataFrame yang kolomnya terus
bertambah setiap iterasi loop komoditas:

    for col in comodity_cols:
        df = lag_transformer.fit_transform(df)      # df melebar
        df = window_transformer.fit_transform(df)   # df melebar lagi

Akibatnya tiap transformer merekam `feature_names_in_` yang berbeda-beda (73,
85, 97, ... 173 kolom) dan `feature-engine` memvalidasi jumlah kolom saat
`transform()`. Memberi DataFrame "seadanya" akan ditolak dengan
`ValueError: The number of columns in this dataset is different ...`.

Solusi: rekonstruksi kerangka DataFrame berisi PERSIS kolom
`feature_names_in_` yang direkam transformer, dengan urutan yang sama. Kolom
yang tidak relevan diisi NaN — transformer hanya menyentuh kolom di
`variables`, yaitu `{komoditas}_residual`. Dengan begitu objek transformer asli
tetap dipakai apa adanya, tanpa akal-akalan.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .artifacts import load_feature_transformers

# Fitur kalender ditulis manual di notebook (cell 41), bukan lewat transformer,
# jadi harus direproduksi dengan rumus yang sama persis.
CALENDAR_FEATURES = ["day_of_week", "month_sin", "month_cos"]

# Jumlah baris riwayat minimum agar lag 30 dan rolling window 30 terisi penuh.
# 30 (lag) + 30 (window) + margin.
MIN_HISTORY_ROWS = 90


def residual_column(name: str) -> str:
    return f"{name}_residual"


def _empty_frame(columns: list[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        np.nan,
        index=index,
        columns=list(columns),
        dtype=float,
    )


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Fitur kalender — replikasi persis notebook cell 41."""
    index = pd.DatetimeIndex(frame.index)
    frame["day_of_week"] = index.dayofweek
    frame["month_sin"] = np.sin(2 * np.pi * index.month / 12)
    frame["month_cos"] = np.cos(2 * np.pi * index.month / 12)
    return frame


def build_feature_frame(name: str, residuals: pd.Series) -> pd.DataFrame:
    """Hasilkan DataFrame berisi seluruh fitur untuk satu komoditas.

    `residuals` harus berindeks DatetimeIndex harian yang kontinu — syarat
    `WindowFeatures(freq='D')` dan syarat kebenaran fitur lag.
    """
    transformers = load_feature_transformers()
    if name not in transformers:
        raise KeyError(f"Komoditas '{name}' tidak ada di features_transformers.pkl")

    lag_tf = transformers[name]["lags"]
    window_tf = transformers[name]["window"]

    index = pd.DatetimeIndex(residuals.index).normalize()
    if index.has_duplicates:
        raise ValueError(f"Indeks tanggal duplikat untuk komoditas '{name}'")

    expected = list(getattr(lag_tf, "feature_names_in_", []))
    if not expected:  # pragma: no cover - transformer lama tanpa metadata
        raise ValueError(
            f"Transformer '{name}' tidak menyimpan feature_names_in_; "
            "artefak perlu dibuat ulang dari notebook."
        )

    frame = _empty_frame(expected, index)
    frame[residual_column(name)] = residuals.to_numpy(dtype=float)

    # Objek transformer asli — bukan tiruan logika.
    frame = lag_tf.transform(frame)
    frame = window_tf.transform(frame)

    return add_calendar_features(frame)


def feature_columns(name: str, frame: pd.DataFrame) -> list[str]:
    """Replikasi `feature_cols_for()` di notebook cell 46.

    Urutan kolom mengikuti urutan kemunculan di DataFrame, sama seperti
    training, karena rantai transformasinya identik.
    """
    lag_prefix = f"{name}_residual_lag_"
    window_prefix = f"{name}_residual_window_"
    cols = [c for c in frame.columns if c.startswith(lag_prefix) or c.startswith(window_prefix)]
    if not cols:
        raise ValueError(f"Fitur untuk {name} tidak ditemukan.")
    return cols + CALENDAR_FEATURES


def build_design_matrix(name: str, residuals: pd.Series) -> tuple[pd.DataFrame, list[str]]:
    """Kembalikan `(X, feature_names)` siap dipakai model."""
    frame = build_feature_frame(name, residuals)
    cols = feature_columns(name, frame)
    return frame[cols], cols
