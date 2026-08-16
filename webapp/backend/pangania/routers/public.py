"""Endpoint sisi publik — tanpa autentikasi, hanya baca."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import HORIZON_DESCRIPTIONS, HORIZON_LABELS, HORIZONS
from ..db import get_db
from ..models import (
    Commodity,
    EwsAlert,
    ModelMetric,
    ModelVersion,
    Prediction,
    Price,
    Projection,
)
from ..services import ews as ews_service
from ..services import projections as projection_service

router = APIRouter(prefix="/api", tags=["public"])

RANGE_DAYS = {"30d": 30, "90d": 90, "1y": 365, "all": None}

# Batas seri sesuai PRD §7.4 — mencegah grafik menyesatkan.
MAX_EXPLORE_SERIES = 3


# ---------------------------------------------------------------------------
# Serialisasi
# ---------------------------------------------------------------------------


def serialize_commodity(commodity: Commodity) -> dict:
    return {
        "id": commodity.id,
        "code": commodity.code,
        "name": commodity.name,
        "family": commodity.family,
        "unit": commodity.unit,
        "color_slot": commodity.color_slot,
        "display_order": commodity.display_order,
    }


def get_commodity_or_404(db: Session, code: str) -> Commodity:
    commodity = db.execute(select(Commodity).where(Commodity.code == code)).scalars().first()
    if commodity is None:
        raise HTTPException(status_code=404, detail=f"Komoditas '{code}' tidak ditemukan.")
    return commodity


def latest_data_date(db: Session) -> date | None:
    return db.execute(select(Price.price_date).order_by(Price.price_date.desc()).limit(1)).scalar_one_or_none()


def _price_rows(db: Session, commodity_id: int, start: date | None, end: date | None) -> list[Price]:
    stmt = select(Price).where(Price.commodity_id == commodity_id)
    if start is not None:
        stmt = stmt.where(Price.price_date >= start)
    if end is not None:
        stmt = stmt.where(Price.price_date <= end)
    return list(db.execute(stmt.order_by(Price.price_date)).scalars())


def _serialize_points(rows: list[Price]) -> list[dict]:
    return [
        {
            "date": row.price_date,
            "price": float(row.price),
            "is_interpolated": bool(row.is_interpolated),
            "source": row.source,
        }
        for row in rows
    ]


def _active_model(db: Session, commodity_id: int, horizon: int) -> ModelVersion | None:
    return db.execute(
        select(ModelVersion).where(
            ModelVersion.commodity_id == commodity_id,
            ModelVersion.horizon == horizon,
            ModelVersion.is_active.is_(True),
        )
    ).scalars().first()


def _serialize_metrics(db: Session, model_version: ModelVersion | None) -> dict | None:
    if model_version is None:
        return None
    metric = db.execute(
        select(ModelMetric)
        .where(ModelMetric.model_version_id == model_version.id)
        .order_by(ModelMetric.evaluated_at.desc())
    ).scalars().first()
    if metric is None:
        return None
    return {
        "split_type": metric.split_type,
        "mae": metric.mae,
        "rmse": metric.rmse,
        "r2": metric.r2,
        "mape": metric.mape,
        "n_samples": metric.n_samples,
    }


def _latest_prediction(db: Session, commodity_id: int, horizon: int) -> Prediction | None:
    return db.execute(
        select(Prediction)
        .where(Prediction.commodity_id == commodity_id, Prediction.horizon == horizon)
        .order_by(Prediction.base_date.desc())
        .limit(1)
    ).scalars().first()


def _serialize_prediction(db: Session, prediction: Prediction | None, horizon: int) -> dict:
    """Prediksi SELALU tampil bersama konteks akurasinya.

    PRD requirement "Transparansi akurasi": prediksi tanpa konteks error
    dianggap cacat produk.
    """
    base = {
        "horizon": horizon,
        "label": HORIZON_LABELS[horizon],
        "description": HORIZON_DESCRIPTIONS[horizon],
        "available": prediction is not None,
    }
    if prediction is None:
        base["reason"] = "Model prediksi untuk horizon ini belum tersedia."
        return base

    model_version = prediction.model_version
    base.update(
        {
            "base_date": prediction.base_date,
            "target_date": prediction.target_date,
            "predicted_price": float(prediction.predicted_price),
            "lower_bound": prediction.lower_bound,
            "upper_bound": prediction.upper_bound,
            "trend_component": prediction.trend_component,
            "seasonal_component": prediction.seasonal_component,
            "predicted_residual": prediction.predicted_residual,
            "model": None
            if model_version is None
            else {
                "id": model_version.id,
                "algorithm": model_version.algorithm,
                "label": model_version.label,
                "trained_at": model_version.trained_at,
                "train_data_end": model_version.train_data_end,
                "hyperparameters": model_version.hyperparameters,
            },
            "metrics": _serialize_metrics(db, model_version),
        }
    )
    return base


# ---------------------------------------------------------------------------
# Meta & master
# ---------------------------------------------------------------------------


@router.get("/meta")
def meta(db: Session = Depends(get_db)) -> dict:
    last = latest_data_date(db)
    total_prices = db.execute(select(Price.id)).scalars().all()
    interpolated = db.execute(select(Price.id).where(Price.is_interpolated.is_(True))).scalars().all()
    active_models = db.execute(
        select(ModelVersion.id).where(ModelVersion.is_active.is_(True))
    ).scalars().all()

    interpolated_pct = (len(interpolated) / len(total_prices) * 100.0) if total_prices else 0.0

    return {
        "app_name": "PANGANIA",
        "region": "Provinsi DIY",
        "data_source": "Bank Indonesia — PIHPS",
        "latest_data_date": last,
        "total_price_rows": len(total_prices),
        "interpolated_rows": len(interpolated),
        "interpolated_pct": round(interpolated_pct, 1),
        "active_model_count": len(active_models),
        "expected_model_count": 9 * len(HORIZONS),
        "horizons": [
            {"value": h, "label": HORIZON_LABELS[h], "description": HORIZON_DESCRIPTIONS[h]}
            for h in HORIZONS
        ],
        # Batasan yang wajib terlihat di antarmuka (PRD §7.6).
        "disclaimers": [
            "Sekitar 30% tanggal adalah hasil interpolasi karena pasar tidak disurvei "
            "pada akhir pekan dan hari libur. Titik ini ditandai khusus pada grafik.",
            "Prediksi bukan jaminan. Setiap angka tampil bersama metrik error modelnya.",
            "Model tidak dilatih ulang secara otomatis; akurasi menurun bila data "
            "terakhir semakin jauh dari akhir periode training.",
            "Estimasi musiman tahunan hanya mencakup sekitar 5,6 siklus — di bawah "
            "rekomendasi ideal untuk dekomposisi musiman tahunan.",
        ],
    }


@router.get("/commodities")
def list_commodities(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    return {"items": [serialize_commodity(c) for c in rows]}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
def dashboard(
    horizon: int = Query(default=1),
    db: Session = Depends(get_db),
) -> dict:
    if horizon not in HORIZONS:
        raise HTTPException(status_code=400, detail=f"Horizon harus salah satu dari {list(HORIZONS)}")

    commodities = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    last_date = latest_data_date(db)
    spark_start = (last_date - timedelta(days=30)) if last_date else None

    cards = []
    alert_counts = {"normal": 0, "waspada": 0, "warning": 0, "kritis": 0, "tidak_tersedia": 0}

    for commodity in commodities:
        rows = _price_rows(db, commodity.id, spark_start, last_date)
        current = rows[-1] if rows else None
        previous = rows[-2] if len(rows) > 1 else None

        delta = delta_pct = None
        if current and previous and previous.price:
            delta = float(current.price) - float(previous.price)
            delta_pct = delta / float(previous.price) * 100.0

        alert = db.execute(
            select(EwsAlert)
            .where(EwsAlert.commodity_id == commodity.id)
            .order_by(EwsAlert.period_month.desc())
            .limit(1)
        ).scalars().first()
        level = alert.level if alert else "tidak_tersedia"
        alert_counts[level] = alert_counts.get(level, 0) + 1

        prediction = _latest_prediction(db, commodity.id, horizon)

        cards.append(
            {
                "commodity": serialize_commodity(commodity),
                "current_price": float(current.price) if current else None,
                "current_date": current.price_date if current else None,
                "delta": delta,
                "delta_pct": delta_pct,
                "sparkline": [float(r.price) for r in rows],
                "sparkline_dates": [r.price_date for r in rows],
                "alert_level": level,
                "alert_label": ews_service.LEVEL_LABELS.get(level, level),
                "prediction": _serialize_prediction(db, prediction, horizon),
            }
        )

    next_target = None
    if last_date:
        next_target = last_date + timedelta(days=horizon)

    return {
        "horizon": horizon,
        "horizon_label": HORIZON_LABELS[horizon],
        "latest_data_date": last_date,
        "next_target_date": next_target,
        "alert_counts": alert_counts,
        "attention_count": alert_counts.get("waspada", 0)
        + alert_counts.get("warning", 0)
        + alert_counts.get("kritis", 0),
        "cards": cards,
    }


# ---------------------------------------------------------------------------
# Detail komoditas
# ---------------------------------------------------------------------------


@router.get("/commodities/{code}")
def commodity_detail(
    code: str,
    range: str = Query(default="90d"),
    db: Session = Depends(get_db),
) -> dict:
    commodity = get_commodity_or_404(db, code)
    if range not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Rentang harus salah satu dari {list(RANGE_DAYS)}")

    last_date = latest_data_date(db)
    days = RANGE_DAYS[range]
    start = (last_date - timedelta(days=days)) if (days and last_date) else None
    rows = _price_rows(db, commodity.id, start, None)

    predictions = [
        _serialize_prediction(db, _latest_prediction(db, commodity.id, h), h) for h in HORIZONS
    ]

    return {
        "commodity": serialize_commodity(commodity),
        "range": range,
        "latest_data_date": last_date,
        "series": _serialize_points(rows),
        "predictions": predictions,
        "statistics": _series_statistics(rows),
    }


def _series_statistics(rows: list[Price]) -> dict:
    if not rows:
        return {"count": 0}
    values = [float(r.price) for r in rows]
    mean = sum(values) / len(values)
    interpolated = sum(1 for r in rows if r.is_interpolated)
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "first": values[0],
        "last": values[-1],
        "change_pct": (values[-1] - values[0]) / values[0] * 100.0 if values[0] else None,
        "interpolated_count": interpolated,
        "interpolated_pct": interpolated / len(rows) * 100.0,
    }


@router.get("/commodities/{code}/accuracy")
def accuracy_history(
    code: str,
    horizon: int = Query(default=1),
    limit: int = Query(default=60, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Riwayat prediksi masa lalu vs realisasi aktual.

    Ini bukti empiris seberapa bisa dipercaya angkanya (PRD fitur #2).
    """
    commodity = get_commodity_or_404(db, code)
    if horizon not in HORIZONS:
        raise HTTPException(status_code=400, detail=f"Horizon harus salah satu dari {list(HORIZONS)}")

    rows = db.execute(
        select(Prediction, Price.price)
        .join(
            Price,
            (Price.commodity_id == Prediction.commodity_id)
            & (Price.price_date == Prediction.target_date),
        )
        .where(Prediction.commodity_id == commodity.id, Prediction.horizon == horizon)
        .order_by(Prediction.target_date.desc())
        .limit(limit)
    ).all()

    items = []
    abs_errors: list[float] = []
    pct_errors: list[float] = []

    for prediction, actual_price in rows:
        actual = float(actual_price)
        predicted = float(prediction.predicted_price)
        error = predicted - actual
        abs_errors.append(abs(error))
        if actual:
            pct_errors.append(abs(error) / actual * 100.0)
        items.append(
            {
                "base_date": prediction.base_date,
                "target_date": prediction.target_date,
                "predicted_price": predicted,
                "actual_price": actual,
                "error": error,
                "error_pct": (error / actual * 100.0) if actual else None,
                "within_bounds": (
                    None
                    if prediction.lower_bound is None or prediction.upper_bound is None
                    else prediction.lower_bound <= actual <= prediction.upper_bound
                ),
            }
        )

    items.reverse()
    summary = {
        "count": len(items),
        "mae": sum(abs_errors) / len(abs_errors) if abs_errors else None,
        "mape": sum(pct_errors) / len(pct_errors) if pct_errors else None,
    }
    return {"commodity": serialize_commodity(commodity), "horizon": horizon, "items": items, "summary": summary}


# ---------------------------------------------------------------------------
# Prediksi interaktif & perbandingan model
# ---------------------------------------------------------------------------


@router.get("/predictions")
def interactive_prediction(
    code: str = Query(...),
    horizon: int = Query(default=1),
    db: Session = Depends(get_db),
) -> dict:
    commodity = get_commodity_or_404(db, code)
    if horizon not in HORIZONS:
        raise HTTPException(status_code=400, detail=f"Horizon harus salah satu dari {list(HORIZONS)}")

    prediction = _latest_prediction(db, commodity.id, horizon)
    last_date = latest_data_date(db)
    rows = _price_rows(db, commodity.id, (last_date - timedelta(days=90)) if last_date else None, None)

    return {
        "commodity": serialize_commodity(commodity),
        "prediction": _serialize_prediction(db, prediction, horizon),
        "recent_series": _serialize_points(rows),
        "latest_data_date": last_date,
    }


@router.get("/models/comparison")
def model_comparison(db: Session = Depends(get_db)) -> dict:
    """Perbandingan GA-LightGBM vs model pembanding (PRD fitur #3).

    Menjawab rumusan masalah #3 secara visual. Selama model pembanding belum
    terdaftar, endpoint mengembalikan daftar kosong beserta penjelasannya —
    bukan angka karangan.
    """
    rows = db.execute(
        select(ModelVersion, ModelMetric)
        .join(ModelMetric, ModelMetric.model_version_id == ModelVersion.id)
        .where(ModelMetric.split_type == "walk_forward")
    ).all()

    buckets: dict[tuple[str, int], list[dict]] = {}
    for model_version, metric in rows:
        key = (model_version.algorithm, model_version.horizon)
        buckets.setdefault(key, []).append(
            {"mae": metric.mae, "rmse": metric.rmse, "r2": metric.r2, "mape": metric.mape}
        )

    def average(values: list[dict], field: str) -> float | None:
        nums = [v[field] for v in values if v[field] is not None]
        return sum(nums) / len(nums) if nums else None

    items = [
        {
            "algorithm": algorithm,
            "horizon": horizon,
            "horizon_label": HORIZON_LABELS.get(horizon, str(horizon)),
            "n_models": len(values),
            "mae": average(values, "mae"),
            "rmse": average(values, "rmse"),
            "r2": average(values, "r2"),
            "mape": average(values, "mape"),
        }
        for (algorithm, horizon), values in sorted(buckets.items())
    ]

    return {
        "items": items,
        "available": bool(items),
        "note": (
            "Metrik dirata-ratakan per algoritma dan horizon dari evaluasi "
            "walk-forward expanding window."
            if items
            else "Belum ada model yang terdaftar beserta metrik evaluasinya."
        ),
    }


# ---------------------------------------------------------------------------
# Eksplorasi data historis
# ---------------------------------------------------------------------------


@router.get("/explore")
def explore(
    codes: str = Query(..., description="Kode komoditas dipisah koma, maksimal 3"),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    wanted = [c.strip() for c in codes.split(",") if c.strip()]
    if not wanted:
        raise HTTPException(status_code=400, detail="Minimal satu komoditas harus dipilih.")
    if len(wanted) > MAX_EXPLORE_SERIES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maksimal {MAX_EXPLORE_SERIES} komoditas dapat dibandingkan sekaligus. "
                "Batas ini menjaga agar warna seri tetap dapat dibedakan, termasuk "
                "oleh pengguna dengan buta warna."
            ),
        )

    series = []
    for code in wanted:
        commodity = get_commodity_or_404(db, code)
        rows = _price_rows(db, commodity.id, start, end)
        series.append(
            {
                "commodity": serialize_commodity(commodity),
                "points": _serialize_points(rows),
                "statistics": _series_statistics(rows),
            }
        )

    return {"series": series, "start": start, "end": end}


@router.get("/explore/decomposition")
def decomposition(
    code: str = Query(...),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Komponen MSTL: Observed, Trend, Seasonal mingguan/tahunan, Residual."""
    from ..config import MODEL_PRICE_SCALE
    from ..ml.artifacts import ArtifactMissingError
    from ..ml.decomposition import get_decomposition

    commodity = get_commodity_or_404(db, code)
    rows = _price_rows(db, commodity.id, start, end)
    if not rows:
        return {"commodity": serialize_commodity(commodity), "available": False, "points": []}

    try:
        decomp = get_decomposition(commodity.name)
    except (ArtifactMissingError, KeyError) as exc:
        return {
            "commodity": serialize_commodity(commodity),
            "available": False,
            "reason": str(exc),
            "points": [],
        }

    points = []
    for row in rows:
        components = decomp.components_at(row.price_date)
        observed = float(row.price)
        trend = components.trend * MODEL_PRICE_SCALE
        weekly = components.seasonal_weekly * MODEL_PRICE_SCALE
        yearly = components.seasonal_yearly * MODEL_PRICE_SCALE
        points.append(
            {
                "date": row.price_date,
                "observed": observed,
                "trend": trend,
                "seasonal_weekly": weekly,
                "seasonal_yearly": yearly,
                "residual": observed - trend - weekly - yearly,
                "is_interpolated": bool(row.is_interpolated),
            }
        )

    return {
        "commodity": serialize_commodity(commodity),
        "available": True,
        "points": points,
        "train_end": decomp.train_end,
    }


@router.get("/export/prices.csv")
def export_prices(
    codes: str | None = None,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    stmt = select(Commodity).order_by(Commodity.display_order)
    if codes:
        wanted = [c.strip() for c in codes.split(",") if c.strip()]
        stmt = stmt.where(Commodity.code.in_(wanted))
    commodities = db.execute(stmt).scalars().all()
    if not commodities:
        raise HTTPException(status_code=404, detail="Tidak ada komoditas yang cocok.")

    by_date: dict[date, dict[int, Price]] = {}
    for commodity in commodities:
        for row in _price_rows(db, commodity.id, start, end):
            by_date.setdefault(row.price_date, {})[commodity.id] = row

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = ["tanggal"]
    for commodity in commodities:
        header.extend([commodity.name, f"{commodity.name} (interpolasi)"])
    writer.writerow(header)

    for day in sorted(by_date):
        line: list = [day.isoformat()]
        for commodity in commodities:
            row = by_date[day].get(commodity.id)
            line.extend(
                [f"{row.price:.2f}" if row else "", "ya" if row and row.is_interpolated else "tidak"]
            )
        writer.writerow(line)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="pangania-harga.csv"'},
    )


# ---------------------------------------------------------------------------
# EWS & proyeksi
# ---------------------------------------------------------------------------


@router.get("/ews")
def ews_overview(
    months: int = Query(default=12, le=60),
    db: Session = Depends(get_db),
) -> dict:
    commodities = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()

    items = []
    for commodity in commodities:
        rows = ews_service.compute_ews_rows(db, commodity)
        recent = rows[-months:] if months else rows
        latest = recent[-1] if recent else None
        items.append(
            {
                "commodity": serialize_commodity(commodity),
                "thresholds": ews_service.resolve_thresholds(db, commodity.id),
                "rows": recent,
                "latest": latest,
            }
        )

    has_predictions = any(
        row.get("has_prediction") for item in items for row in item["rows"]
    )

    return {
        "items": items,
        "level_labels": ews_service.LEVEL_LABELS,
        "has_prediction_component": has_predictions,
        "note": (
            "Status bersifat indikatif, bukan keputusan kebijakan."
            if has_predictions
            else "Komponen perbandingan prediksi H+30 belum tersedia karena model "
            "prediksi belum terdaftar. Z-score dihitung dari realisasi aktual saja."
        ),
    }


@router.get("/projections")
def projections(
    years: int = Query(default=3),
    db: Session = Depends(get_db),
) -> dict:
    if years not in projection_service.PROJECTION_YEARS:
        raise HTTPException(
            status_code=400,
            detail=f"Horizon proyeksi harus salah satu dari {list(projection_service.PROJECTION_YEARS)}",
        )

    commodities = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    items = []
    for commodity in commodities:
        payload = projection_service.compute_projection(db, commodity, years)
        if payload is None:
            continue
        items.append({"commodity": serialize_commodity(commodity), **payload})

    return {
        "years": years,
        "items": items,
        "disclaimer": (
            "Proyeksi ini BUKAN keluaran model LightGBM. Angka dihitung dari CAGR "
            "historis dan ekstrapolasi trend model, sehingga bersifat indikasi laju "
            "kenaikan — bukan prediksi harga presisi. Ketidakpastian melebar seiring "
            "jauhnya horizon."
        ),
    }


@router.get("/projections/stored")
def stored_projections(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Projection).order_by(Projection.commodity_id, Projection.horizon_years)).scalars().all()
    return {
        "items": [
            {
                "commodity_id": row.commodity_id,
                "horizon_years": row.horizon_years,
                "cagr": row.cagr,
                "base_price": row.base_price,
                "projected_price": row.projected_price,
                "lower_bound": row.lower_bound,
                "upper_bound": row.upper_bound,
                "computed_at": row.computed_at,
            }
            for row in rows
        ]
    }
