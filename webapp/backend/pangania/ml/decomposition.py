"""Rekonstruksi komponen dekomposisi MSTL untuk kebutuhan inference.

KONSISTENSI DENGAN TRAINING — dibaca dulu sebelum mengubah berkas ini.

Saat training (notebook cell 36), residual didefinisikan sebagai keluaran MSTL:

    residual = observed - trend - seasonal_7 - seasonal_365

Model LightGBM dilatih untuk memprediksi residual tersebut. Karena itu, agar
inference konsisten, residual pada data baru WAJIB dihitung dengan rumus yang
sama, dan rekonstruksi harga wajib menjumlahkan kembali ketiga komponen:

    harga = residual_prediksi + trend + seasonal_7 + seasonal_365

Catatan: potongan kode di `workflow-program.md` step 13 menuliskan
`residual = harga_aktual - trend_baru` saja, tanpa komponen musiman. Itu tidak
konsisten dengan definisi residual di step 4 dan akan membuat masukan model
bergeser secara sistematis sebesar komponen musiman. Modul ini mengikuti
definisi step 4 (yang dipakai saat training), bukan potongan step 13.

Sumber komponen:
  * Dalam rentang data training  -> nilai persis dari `stl_results.pkl`.
  * Di luar rentang data training -> trend diekstrapolasi lewat `trend_models.pkl`
    (LinearRegression atas `time_index`), sedangkan komponen musiman
    diekstrapolasi secara periodik dari siklus penuh terakhir. MSTL sendiri
    hanya alat dekomposisi, bukan model peramalan — ia tidak bisa
    diekstrapolasi langsung.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

import numpy as np
import pandas as pd

from ..config import MODEL_PRICE_SCALE, SERIES_START_DATE
from .artifacts import load_stl_results, load_trend_models

logger = logging.getLogger(__name__)

WEEKLY_PERIOD = 7
YEARLY_PERIOD = 365

_SERIES_START = pd.Timestamp(SERIES_START_DATE)


def time_index_for(day: date | datetime | pd.Timestamp) -> int:
    """`time_index` yang dipakai `trend_models`.

    Di notebook, `time_index = np.arange(len(df_cleaned))` pada indeks harian
    yang kontinu mulai 2021-01-04. Jadi time_index sebuah tanggal sama dengan
    jumlah hari sejak tanggal awal deret.
    """
    return int((pd.Timestamp(day).normalize() - _SERIES_START).days)


def time_index_series(index: pd.DatetimeIndex) -> np.ndarray:
    return ((index.normalize() - _SERIES_START).days).to_numpy(dtype=float)


@dataclass(frozen=True)
class Components:
    """Komponen dekomposisi dalam SKALA MODEL (ribu rupiah)."""

    trend: float
    seasonal_weekly: float
    seasonal_yearly: float

    @property
    def seasonal(self) -> float:
        return self.seasonal_weekly + self.seasonal_yearly

    @property
    def baseline(self) -> float:
        """Bagian harga yang dijelaskan komponen deterministik."""
        return self.trend + self.seasonal


class CommodityDecomposition:
    """Penyedia komponen dekomposisi untuk satu komoditas."""

    def __init__(self, name: str) -> None:
        self.name = name
        stl = load_stl_results()
        trend_models = load_trend_models()
        if name not in stl:
            raise KeyError(f"Komoditas '{name}' tidak ada di stl_results.pkl")
        if name not in trend_models:
            raise KeyError(f"Komoditas '{name}' tidak ada di trend_models.pkl")

        result = stl[name]
        self.trend_model = trend_models[name]

        seasonal = result.seasonal
        if isinstance(seasonal, pd.DataFrame):
            weekly = seasonal.iloc[:, 0]
            yearly = seasonal.iloc[:, 1] if seasonal.shape[1] > 1 else pd.Series(0.0, index=seasonal.index)
        else:  # pragma: no cover - MSTL dengan satu periode
            weekly = seasonal
            yearly = pd.Series(0.0, index=seasonal.index)

        self._index: pd.DatetimeIndex = pd.DatetimeIndex(result.trend.index).normalize()
        self._trend = pd.Series(np.asarray(result.trend, dtype=float), index=self._index)
        self._weekly = pd.Series(np.asarray(weekly, dtype=float), index=self._index)
        self._yearly = pd.Series(np.asarray(yearly, dtype=float), index=self._index)

        self.train_start: date = self._index.min().date()
        self.train_end: date = self._index.max().date()

        # Peta ekstrapolasi periodik: time_index modulo periode -> nilai musiman
        # dari siklus penuh TERAKHIR. Ini ekstrapolasi periodik yang eksak,
        # bukan tebakan — komponen musiman MSTL memang berulang per periode.
        self._weekly_cycle = self._build_cycle(self._weekly, WEEKLY_PERIOD)
        self._yearly_cycle = self._build_cycle(self._yearly, YEARLY_PERIOD)

    @staticmethod
    def _build_cycle(series: pd.Series, period: int) -> dict[int, float]:
        tail = series.iloc[-period:]
        cycle: dict[int, float] = {}
        for ts, value in tail.items():
            cycle[time_index_for(ts) % period] = float(value)
        return cycle

    # -- akses per tanggal --------------------------------------------------

    def trend_at(self, day: date) -> float:
        ts = pd.Timestamp(day).normalize()
        if ts in self._trend.index:
            return float(self._trend.loc[ts])
        # Di luar rentang training -> ekstrapolasi linear (step 4 & 11).
        frame = pd.DataFrame({"time_index": [float(time_index_for(ts))]})
        return float(self.trend_model.predict(frame)[0])

    def seasonal_at(self, day: date) -> tuple[float, float]:
        ts = pd.Timestamp(day).normalize()
        if ts in self._weekly.index:
            return float(self._weekly.loc[ts]), float(self._yearly.loc[ts])
        ti = time_index_for(ts)
        weekly = self._weekly_cycle.get(ti % WEEKLY_PERIOD, 0.0)
        yearly = self._yearly_cycle.get(ti % YEARLY_PERIOD, 0.0)
        return weekly, yearly

    def components_at(self, day: date) -> Components:
        weekly, yearly = self.seasonal_at(day)
        return Components(trend=self.trend_at(day), seasonal_weekly=weekly, seasonal_yearly=yearly)

    # -- akses vektor (dipakai untuk membangun deret residual) --------------

    def baseline_series(self, index: pd.DatetimeIndex) -> pd.Series:
        """Komponen deterministik (trend + musiman) untuk setiap tanggal di `index`."""
        index = pd.DatetimeIndex(index).normalize()
        known = index.intersection(self._index)
        unknown = index.difference(self._index)

        values = pd.Series(np.nan, index=index, dtype=float)

        if len(known) > 0:
            values.loc[known] = (
                self._trend.loc[known] + self._weekly.loc[known] + self._yearly.loc[known]
            ).to_numpy(dtype=float)

        if len(unknown) > 0:
            ti = time_index_series(unknown)
            trend = self.trend_model.predict(pd.DataFrame({"time_index": ti}))
            weekly = np.array([self._weekly_cycle.get(int(t) % WEEKLY_PERIOD, 0.0) for t in ti])
            yearly = np.array([self._yearly_cycle.get(int(t) % YEARLY_PERIOD, 0.0) for t in ti])
            values.loc[unknown] = np.asarray(trend, dtype=float) + weekly + yearly

        return values

    def residual_series(self, prices_model_scale: pd.Series) -> pd.Series:
        """residual = harga - trend - seasonal_weekly - seasonal_yearly.

        `prices_model_scale` sudah dalam skala model (ribu rupiah).
        """
        index = pd.DatetimeIndex(prices_model_scale.index).normalize()
        baseline = self.baseline_series(index)
        return pd.Series(prices_model_scale.to_numpy(dtype=float), index=index) - baseline

    def drift_days(self, reference: date) -> int:
        """Jarak hari antara `reference` dan akhir periode training.

        Dipakai untuk peringatan trend extrapolation drift (PRD §7.6 poin 1).
        """
        return max(0, (reference - self.train_end).days)


@lru_cache(maxsize=16)
def get_decomposition(name: str) -> CommodityDecomposition:
    return CommodityDecomposition(name)


def to_model_scale(price_rupiah: float) -> float:
    return float(price_rupiah) / MODEL_PRICE_SCALE


def to_rupiah(price_model_scale: float) -> float:
    return float(price_model_scale) * MODEL_PRICE_SCALE
