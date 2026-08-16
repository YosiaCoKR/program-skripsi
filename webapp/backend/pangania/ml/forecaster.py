"""Rolling One-Step Forecast — lapisan inference (workflow step 13).

TITIK INTEGRASI MODEL
---------------------
Seluruh pipeline di bawah ini sudah lengkap dan siap pakai. Yang belum ada
hanyalah artefak model prediksi (27 berkas LightGBM hasil GA, komoditas x
horizon) karena masih dikerjakan di notebook.

Begitu artefak tersedia, daftarkan lewat panel admin "Manajemen Model" atau
skrip `scripts/register_model.py`. Tidak ada kode yang perlu diubah — modul ini
otomatis memakai `ModelVersion` yang `is_active` untuk tiap pasangan
(komoditas, horizon).

Selama model belum terdaftar, `run_forecast()` tetap berjalan dan mencatat
`ForecastRun` berstatus `partial`/`failed` dengan pesan yang jelas, sehingga
antarmuka bisa menampilkan keadaan "model belum tersedia" secara jujur alih-alih
menampilkan angka palsu.

BUKAN RECURSIVE FORECASTING
---------------------------
Fitur lag/rolling selalu dibangun dari tabel `prices` (harga AKTUAL). Hasil
prediksi tidak pernah menjadi masukan prediksi berikutnya. Yang berubah tiap
hari hanyalah kapan model dipanggil ulang, bukan sumber datanya.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import HORIZONS, MODEL_PRICE_SCALE
from ..models import Commodity, ForecastRun, ModelMetric, ModelVersion, Prediction, Price
from .artifacts import ArtifactMissingError, load_prediction_model
from .decomposition import get_decomposition
from .features import MIN_HISTORY_ROWS, build_design_matrix

logger = logging.getLogger(__name__)

# Jumlah hari riwayat yang diambil untuk membentuk fitur. Lebih panjang dari
# kebutuhan minimum supaya rolling window 30 hari terisi penuh.
HISTORY_WINDOW_DAYS = 180

# Faktor interval ketidakpastian (~95%) dari RMSE model.
UNCERTAINTY_Z = 1.96


@dataclass
class ForecastItem:
    commodity_id: int
    commodity_name: str
    horizon: int
    base_date: date
    target_date: date
    predicted_price: float
    predicted_residual: float
    trend_component: float
    seasonal_component: float
    lower_bound: float | None = None
    upper_bound: float | None = None
    model_version_id: int | None = None


@dataclass
class ForecastOutcome:
    items: list[ForecastItem] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.errors and not self.items:
            return "failed"
        if self.skipped or self.errors:
            return "partial"
        return "success"


class NoActiveModelError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Pengambilan data
# ---------------------------------------------------------------------------


def load_price_series(db: Session, commodity: Commodity, base_date: date) -> pd.Series:
    """Deret harga AKTUAL harian sampai `base_date`, dalam skala model.

    Indeks dipastikan harian dan kontinu — syarat `WindowFeatures(freq='D')`.
    Tanggal yang tidak ada baris harganya diisi lewat interpolasi berbasis
    waktu, konsisten dengan penanganan missing value di penelitian (step 2).
    """
    start = base_date - timedelta(days=HISTORY_WINDOW_DAYS)
    rows = db.execute(
        select(Price.price_date, Price.price)
        .where(
            Price.commodity_id == commodity.id,
            Price.price_date >= start,
            Price.price_date <= base_date,
        )
        .order_by(Price.price_date)
    ).all()

    if not rows:
        raise ValueError(f"Tidak ada data harga untuk {commodity.name} sampai {base_date}")

    series = pd.Series(
        {pd.Timestamp(r.price_date): float(r.price) for r in rows},
        dtype=float,
    ).sort_index()

    full_index = pd.date_range(series.index.min(), pd.Timestamp(base_date), freq="D")
    series = series.reindex(full_index).interpolate(method="time", limit_direction="both")

    if len(series) < MIN_HISTORY_ROWS:
        raise ValueError(
            f"Riwayat {commodity.name} hanya {len(series)} hari, "
            f"minimal {MIN_HISTORY_ROWS} hari dibutuhkan untuk fitur lag/rolling"
        )

    # Skala model: dataset penelitian memakai satuan ribu rupiah.
    return series / MODEL_PRICE_SCALE


def get_active_models(db: Session) -> dict[tuple[int, int], ModelVersion]:
    rows = db.execute(select(ModelVersion).where(ModelVersion.is_active.is_(True))).scalars().all()
    return {(m.commodity_id, m.horizon): m for m in rows}


def _residual_rmse(db: Session, model_version_id: int) -> float | None:
    """RMSE walk-forward dalam skala model, dipakai untuk pita ketidakpastian."""
    metric = db.execute(
        select(ModelMetric)
        .where(
            ModelMetric.model_version_id == model_version_id,
            ModelMetric.split_type == "walk_forward",
        )
        .order_by(ModelMetric.evaluated_at.desc())
    ).scalars().first()
    if metric is None or metric.rmse is None:
        return None
    return float(metric.rmse)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


def forecast_commodity(
    db: Session,
    commodity: Commodity,
    base_date: date,
    active_models: dict[tuple[int, int], ModelVersion],
) -> tuple[list[ForecastItem], list[str], list[str]]:
    items: list[ForecastItem] = []
    skipped: list[str] = []
    errors: list[str] = []

    decomposition = get_decomposition(commodity.name)
    prices = load_price_series(db, commodity, base_date)
    residuals = decomposition.residual_series(prices)

    design, feature_names = build_design_matrix(commodity.name, residuals)
    latest = design.iloc[[-1]]

    if latest.isna().any(axis=None):
        missing = [c for c in latest.columns if pd.isna(latest.iloc[0][c])]
        errors.append(
            f"{commodity.name}: fitur belum lengkap pada {base_date} "
            f"({len(missing)} fitur kosong, mis. {missing[:3]})"
        )
        return items, skipped, errors

    for horizon in HORIZONS:
        model_version = active_models.get((commodity.id, horizon))
        if model_version is None or not model_version.artifact_path:
            skipped.append(f"{commodity.name} H+{horizon}: belum ada model aktif")
            continue

        try:
            model = load_prediction_model(model_version.artifact_path)
        except ArtifactMissingError as exc:
            errors.append(f"{commodity.name} H+{horizon}: {exc}")
            continue

        # Urutan kolom mengikuti yang direkam saat model dilatih; kalau tidak
        # ada, pakai urutan hasil pipeline (identik dengan notebook).
        cols = list(model_version.feature_names) or feature_names
        try:
            X = latest[cols]
        except KeyError as exc:
            errors.append(f"{commodity.name} H+{horizon}: fitur model tidak cocok ({exc})")
            continue

        try:
            residual_pred = float(np.asarray(model.predict(X)).ravel()[0])
        except Exception as exc:  # pragma: no cover - bergantung artefak
            errors.append(f"{commodity.name} H+{horizon}: gagal prediksi ({exc})")
            continue

        target_date = base_date + timedelta(days=horizon)
        components = decomposition.components_at(target_date)

        price_model_scale = residual_pred + components.baseline
        predicted_price = price_model_scale * MODEL_PRICE_SCALE

        rmse = _residual_rmse(db, model_version.id)
        lower = upper = None
        if rmse is not None:
            margin = UNCERTAINTY_Z * rmse * MODEL_PRICE_SCALE
            lower = predicted_price - margin
            upper = predicted_price + margin

        items.append(
            ForecastItem(
                commodity_id=commodity.id,
                commodity_name=commodity.name,
                horizon=horizon,
                base_date=base_date,
                target_date=target_date,
                predicted_price=predicted_price,
                predicted_residual=residual_pred,
                trend_component=components.trend * MODEL_PRICE_SCALE,
                seasonal_component=components.seasonal * MODEL_PRICE_SCALE,
                lower_bound=lower,
                upper_bound=upper,
                model_version_id=model_version.id,
            )
        )

    return items, skipped, errors


def persist_predictions(db: Session, run: ForecastRun, items: list[ForecastItem]) -> int:
    """Simpan prediksi secara idempoten per (komoditas, horizon, base_date)."""
    count = 0
    for item in items:
        existing = db.execute(
            select(Prediction).where(
                Prediction.commodity_id == item.commodity_id,
                Prediction.horizon == item.horizon,
                Prediction.base_date == item.base_date,
            )
        ).scalars().first()

        if existing is None:
            existing = Prediction(
                commodity_id=item.commodity_id,
                horizon=item.horizon,
                base_date=item.base_date,
            )
            db.add(existing)

        existing.target_date = item.target_date
        existing.predicted_price = item.predicted_price
        existing.predicted_residual = item.predicted_residual
        existing.trend_component = item.trend_component
        existing.seasonal_component = item.seasonal_component
        existing.lower_bound = item.lower_bound
        existing.upper_bound = item.upper_bound
        existing.model_version_id = item.model_version_id
        existing.forecast_run_id = run.id
        count += 1

    return count


def run_forecast(
    db: Session,
    base_date: date,
    *,
    user_id: int | None = None,
    trigger_type: str = "price_input",
    commodity_ids: list[int] | None = None,
) -> ForecastRun:
    """Jalankan rolling one-step forecast untuk seluruh horizon.

    Kegagalan inference TIDAK boleh membatalkan penyimpanan harga (PRD §5
    catatan #4). Fungsi ini karena itu selalu mengembalikan `ForecastRun`,
    bukan melempar exception ke pemanggil.
    """
    run = ForecastRun(
        base_date=base_date,
        status="pending",
        trigger_type=trigger_type,
        triggered_by=user_id,
    )
    db.add(run)
    db.flush()

    outcome = ForecastOutcome()

    stmt = select(Commodity).order_by(Commodity.display_order)
    if commodity_ids:
        stmt = stmt.where(Commodity.id.in_(commodity_ids))
    commodities = db.execute(stmt).scalars().all()

    active_models = get_active_models(db)

    if not active_models:
        outcome.skipped.append(
            "Belum ada model prediksi yang aktif. Daftarkan artefak model "
            "(27 berkas: 9 komoditas x 3 horizon) lewat menu Manajemen Model."
        )

    for commodity in commodities:
        try:
            items, skipped, errors = forecast_commodity(db, commodity, base_date, active_models)
            outcome.items.extend(items)
            outcome.skipped.extend(skipped)
            outcome.errors.extend(errors)
        except (ArtifactMissingError, KeyError, ValueError) as exc:
            outcome.errors.append(f"{commodity.name}: {exc}")
        except Exception as exc:  # pragma: no cover - jaring pengaman
            logger.exception("Forecast gagal untuk %s", commodity.name)
            outcome.errors.append(f"{commodity.name}: kesalahan tak terduga ({exc})")

    run.predictions_count = persist_predictions(db, run, outcome.items)
    run.status = outcome.status
    run.finished_at = datetime.now()

    messages = outcome.errors + outcome.skipped
    run.error_message = "\n".join(messages[:40]) if messages else None

    db.flush()
    return run
