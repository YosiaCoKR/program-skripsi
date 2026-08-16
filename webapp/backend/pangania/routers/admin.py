"""Endpoint sisi admin — seluruhnya memerlukan sesi admin."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..config import (
    DRIFT_CRITICAL_DAYS,
    DRIFT_WARNING_DAYS,
    HORIZON_LABELS,
    HORIZONS,
    OUTLIER_PCT_THRESHOLD,
)
from ..db import get_db
from ..deps import require_admin
from ..models import (
    AuditLog,
    Commodity,
    EwsSetting,
    ForecastRun,
    ModelMetric,
    ModelVersion,
    Prediction,
    Price,
    User,
)
from ..schemas import (
    DailyPriceRequest,
    EwsPreviewRequest,
    EwsSettingRequest,
    ForecastRunRequest,
    ModelMetricRequest,
    ModelVersionRequest,
    PriceUpdateRequest,
)
from ..services import audit
from ..services import ews as ews_service
from ..services import prices as price_service
from ..services import projections as projection_service
from .public import serialize_commodity

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _run_forecast_safely(db: Session, base_date: date, user_id: int, trigger_type: str) -> dict:
    """Jalankan forecast tanpa pernah membatalkan penyimpanan harga.

    PRD §5 catatan #4: kegagalan lapisan inference tidak boleh menggagalkan
    transaksi harga yang sudah tersimpan.
    """
    try:
        from ..ml.forecaster import run_forecast

        run = run_forecast(db, base_date, user_id=user_id, trigger_type=trigger_type)
        return {
            "id": run.id,
            "status": run.status,
            "predictions_count": run.predictions_count,
            "message": run.error_message,
        }
    except Exception as exc:  # pragma: no cover - jaring pengaman
        return {"id": None, "status": "failed", "predictions_count": 0, "message": str(exc)}


# ---------------------------------------------------------------------------
# Beranda admin
# ---------------------------------------------------------------------------


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    last_date = price_service.latest_price_date(db)
    today = date.today()

    missing_dates: list[date] = []
    if last_date and last_date < today:
        missing_dates = [last_date + timedelta(days=n) for n in range(1, (today - last_date).days + 1)]

    active_models = db.execute(
        select(ModelVersion).where(ModelVersion.is_active.is_(True))
    ).scalars().all()
    expected = len(HORIZONS) * db.execute(select(func.count(Commodity.id))).scalar_one()

    # Trend extrapolation drift (PRD §7.6 poin 1).
    train_ends = [m.train_data_end for m in active_models if m.train_data_end]
    drift_days = None
    drift_level = "unknown"
    if train_ends and last_date:
        drift_days = max(0, (last_date - max(train_ends)).days)
        if drift_days >= DRIFT_CRITICAL_DAYS:
            drift_level = "kritis"
        elif drift_days >= DRIFT_WARNING_DAYS:
            drift_level = "peringatan"
        else:
            drift_level = "aman"

    recent_runs = db.execute(
        select(ForecastRun).order_by(desc(ForecastRun.started_at)).limit(5)
    ).scalars().all()

    return {
        "latest_data_date": last_date,
        "today": today,
        "missing_dates": missing_dates,
        "missing_count": len(missing_dates),
        "active_model_count": len(active_models),
        "expected_model_count": expected,
        "models_ready": len(active_models) >= expected,
        "drift": {
            "days": drift_days,
            "level": drift_level,
            "warning_threshold": DRIFT_WARNING_DAYS,
            "critical_threshold": DRIFT_CRITICAL_DAYS,
        },
        "recent_runs": [
            {
                "id": r.id,
                "base_date": r.base_date,
                "status": r.status,
                "predictions_count": r.predictions_count,
                "started_at": r.started_at,
            }
            for r in recent_runs
        ],
    }


# ---------------------------------------------------------------------------
# Input harga
# ---------------------------------------------------------------------------


@router.get("/prices/prefill")
def prefill(
    target_date: date = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Nilai awal form input harian.

    Terisi harga hari sebelumnya karena harga sering tidak berubah — tapi tetap
    harus dikonfirmasi admin (PRD fitur #8).
    """
    commodities = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    items = []
    for commodity in commodities:
        existing = price_service.price_on(db, commodity.id, target_date)
        previous = price_service.previous_price(db, commodity.id, target_date)
        items.append(
            {
                "commodity": serialize_commodity(commodity),
                "existing_price": float(existing.price) if existing else None,
                "previous_price": float(previous.price) if previous else None,
                "previous_date": previous.price_date if previous else None,
                "suggested_price": float(existing.price)
                if existing
                else (float(previous.price) if previous else None),
            }
        )

    return {
        "target_date": target_date,
        "items": items,
        "gap_dates": price_service.detect_gap(db, target_date),
        "outlier_threshold_pct": OUTLIER_PCT_THRESHOLD,
    }


@router.post("/prices/daily")
def save_daily(
    payload: DailyPriceRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    entries = {entry.commodity_id: entry.price for entry in payload.entries}

    known = set(db.execute(select(Commodity.id)).scalars())
    unknown = set(entries) - known
    if unknown:
        raise HTTPException(status_code=400, detail=f"commodity_id tidak dikenal: {sorted(unknown)}")

    # Peringatan outlier dikembalikan lebih dulu supaya admin bisa
    # mengonfirmasi. Ini memperingatkan, bukan memblokir.
    warnings = price_service.check_outliers(db, entries, payload.price_date)
    if warnings and not payload.confirm_outliers:
        return {
            "status": "needs_confirmation",
            "warnings": [
                {
                    "commodity_id": w.commodity_id,
                    "commodity_name": w.commodity_name,
                    "previous_price": w.previous_price,
                    "new_price": w.new_price,
                    "change_pct": w.change_pct,
                }
                for w in warnings
            ],
            "gap_dates": price_service.detect_gap(db, payload.price_date),
            "message": (
                f"Terdapat {len(warnings)} harga yang menyimpang lebih dari "
                f"{OUTLIER_PCT_THRESHOLD:.0f}% dari hari sebelumnya. Periksa kembali, "
                "lalu simpan ulang dengan konfirmasi bila memang benar."
            ),
        }

    result = price_service.save_daily_prices(
        db,
        target_date=payload.price_date,
        entries=entries,
        user_id=user.id,
        fill_gaps=payload.fill_gaps,
    )
    db.commit()

    forecast = None
    if payload.run_forecast:
        forecast = _run_forecast_safely(db, payload.price_date, user.id, "price_input")
        ews_service.rebuild_alerts(db)
        db.commit()

    return {
        "status": "saved",
        "saved": result.saved,
        "updated": result.updated,
        "interpolated": result.interpolated,
        "gap_dates": result.gap_dates,
        "forecast": forecast,
    }


@router.post("/prices/import")
def import_csv(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict:
    """Impor banyak tanggal sekaligus.

    `commit=false` menghasilkan pratinjau beserta laporan baris yang ditolak,
    tanpa menulis apa pun (PRD fitur #8 mode Impor CSV).
    """
    rows = payload.get("rows") or []
    commit = bool(payload.get("commit"))

    commodities = {c.name: c for c in db.execute(select(Commodity)).scalars()}
    accepted: list[dict] = []
    rejected: list[dict] = []

    for index, raw in enumerate(rows):
        raw_date = raw.get("price_date") or raw.get("tanggal")
        try:
            parsed_date = date.fromisoformat(str(raw_date))
        except (TypeError, ValueError):
            rejected.append({"row": index + 1, "reason": f"Tanggal tidak valid: {raw_date!r}"})
            continue

        values = raw.get("values") or {}
        entries: dict[int, float] = {}
        row_errors: list[str] = []

        for name, value in values.items():
            commodity = commodities.get(name)
            if commodity is None:
                row_errors.append(f"kolom '{name}' tidak dikenal")
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                row_errors.append(f"nilai '{name}' bukan angka")
                continue
            if numeric <= 0:
                row_errors.append(f"nilai '{name}' harus lebih dari 0")
                continue
            entries[commodity.id] = numeric

        if row_errors:
            rejected.append({"row": index + 1, "date": parsed_date, "reason": "; ".join(row_errors)})
            continue
        if not entries:
            rejected.append({"row": index + 1, "date": parsed_date, "reason": "tidak ada nilai valid"})
            continue

        accepted.append({"date": parsed_date, "entries": entries})

    if not commit:
        return {
            "status": "preview",
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "rejected": rejected[:50],
            "date_range": (
                {"start": min(a["date"] for a in accepted), "end": max(a["date"] for a in accepted)}
                if accepted
                else None
            ),
        }

    saved = updated = interpolated = 0
    for item in sorted(accepted, key=lambda a: a["date"]):
        result = price_service.save_daily_prices(
            db,
            target_date=item["date"],
            entries=item["entries"],
            user_id=user.id,
            fill_gaps=True,
            source="pihps",
        )
        saved += result.saved
        updated += result.updated
        interpolated += result.interpolated

    db.commit()

    forecast = None
    if accepted and payload.get("run_forecast", True):
        forecast = _run_forecast_safely(db, max(a["date"] for a in accepted), user.id, "price_input")
        ews_service.rebuild_alerts(db)
        projection_service.rebuild_projections(db)
        db.commit()

    return {
        "status": "committed",
        "saved": saved,
        "updated": updated,
        "interpolated": interpolated,
        "rejected_count": len(rejected),
        "rejected": rejected[:50],
        "forecast": forecast,
    }


# ---------------------------------------------------------------------------
# Riwayat & koreksi
# ---------------------------------------------------------------------------


@router.get("/prices")
def list_prices(
    commodity_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    only_interpolated: bool = False,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Price)
    count_stmt = select(func.count(Price.id))
    for condition in (
        (Price.commodity_id == commodity_id) if commodity_id else None,
        (Price.price_date >= start) if start else None,
        (Price.price_date <= end) if end else None,
        Price.is_interpolated.is_(True) if only_interpolated else None,
    ):
        if condition is not None:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

    total = db.execute(count_stmt).scalar_one()
    rows = db.execute(
        stmt.order_by(desc(Price.price_date), Price.commodity_id).limit(limit).offset(offset)
    ).scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": row.id,
                "commodity_id": row.commodity_id,
                "commodity_name": row.commodity.name,
                "price_date": row.price_date,
                "price": float(row.price),
                "source": row.source,
                "is_interpolated": row.is_interpolated,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
    }


@router.put("/prices/{price_id}")
def update_price(
    price_id: int,
    payload: PriceUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    row = db.get(Price, price_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Data harga tidak ditemukan.")

    before = {"price": float(row.price), "is_interpolated": row.is_interpolated, "source": row.source}
    row.price = payload.price
    row.is_interpolated = False
    row.source = "manual"
    audit.record(
        db,
        user_id=user.id,
        action="update",
        entity="price",
        entity_id=row.id,
        before=before,
        after={"price": payload.price, "is_interpolated": False, "source": "manual"},
    )
    db.commit()

    forecast = None
    if payload.run_forecast:
        forecast = _run_forecast_safely(db, row.price_date, user.id, "price_correction")
        ews_service.rebuild_alerts(db, [row.commodity_id])
        db.commit()

    return {"status": "updated", "forecast": forecast}


@router.delete("/prices/{price_id}")
def delete_price(
    price_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    row = db.get(Price, price_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Data harga tidak ditemukan.")

    audit.record(
        db,
        user_id=user.id,
        action="delete",
        entity="price",
        entity_id=row.id,
        before={
            "commodity_id": row.commodity_id,
            "price_date": row.price_date,
            "price": float(row.price),
        },
    )
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Monitor rolling forecast
# ---------------------------------------------------------------------------


@router.get("/forecast-runs")
def list_runs(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(
        select(ForecastRun).order_by(desc(ForecastRun.started_at)).limit(limit)
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "base_date": r.base_date,
                "status": r.status,
                "trigger_type": r.trigger_type,
                "predictions_count": r.predictions_count,
                "error_message": r.error_message,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "duration_seconds": (
                    (r.finished_at - r.started_at).total_seconds() if r.finished_at else None
                ),
            }
            for r in rows
        ]
    }


@router.post("/forecast-runs")
def trigger_run(
    payload: ForecastRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    base_date = payload.base_date or price_service.latest_price_date(db)
    if base_date is None:
        raise HTTPException(status_code=400, detail="Belum ada data harga untuk dijadikan tanggal basis.")

    result = _run_forecast_safely(db, base_date, user.id, "manual_rerun")
    ews_service.rebuild_alerts(db)
    db.commit()
    return {"base_date": base_date, "forecast": result}


# ---------------------------------------------------------------------------
# Manajemen model
# ---------------------------------------------------------------------------


@router.get("/models")
def list_models(db: Session = Depends(get_db)) -> dict:
    commodities = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    versions = db.execute(select(ModelVersion).order_by(desc(ModelVersion.trained_at))).scalars().all()

    by_slot: dict[tuple[int, int], list[ModelVersion]] = {}
    for version in versions:
        by_slot.setdefault((version.commodity_id, version.horizon), []).append(version)

    matrix = []
    for commodity in commodities:
        for horizon in HORIZONS:
            slot_versions = by_slot.get((commodity.id, horizon), [])
            active = next((v for v in slot_versions if v.is_active), None)
            matrix.append(
                {
                    "commodity": serialize_commodity(commodity),
                    "horizon": horizon,
                    "horizon_label": HORIZON_LABELS[horizon],
                    "has_active": active is not None,
                    "active": None
                    if active is None
                    else {
                        "id": active.id,
                        "algorithm": active.algorithm,
                        "label": active.label,
                        "artifact_path": active.artifact_path,
                        "hyperparameters": active.hyperparameters,
                        "train_data_end": active.train_data_end,
                        "trained_at": active.trained_at,
                        "metrics": [
                            {
                                "split_type": m.split_type,
                                "mae": m.mae,
                                "rmse": m.rmse,
                                "r2": m.r2,
                                "mape": m.mape,
                            }
                            for m in active.metrics
                        ],
                    },
                    "version_count": len(slot_versions),
                }
            )

    from ..ml.artifacts import artifact_status

    return {
        "matrix": matrix,
        "expected_count": len(commodities) * len(HORIZONS),
        "active_count": sum(1 for entry in matrix if entry["has_active"]),
        "research_artifacts": artifact_status(),
    }


@router.post("/models")
def register_model(
    payload: ModelVersionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    commodity = db.get(Commodity, payload.commodity_id)
    if commodity is None:
        raise HTTPException(status_code=404, detail="Komoditas tidak ditemukan.")

    from ..config import MODEL_DIR

    artifact_file = MODEL_DIR / payload.artifact_path
    if not artifact_file.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Artefak '{payload.artifact_path}' tidak ditemukan di {MODEL_DIR}. "
                "Salin berkas model ke direktori tersebut lebih dulu."
            ),
        )

    version = ModelVersion(
        commodity_id=payload.commodity_id,
        horizon=payload.horizon,
        algorithm=payload.algorithm,
        label=payload.label or f"{payload.algorithm} H+{payload.horizon}",
        artifact_path=payload.artifact_path,
        hyperparameters=payload.hyperparameters,
        feature_names=payload.feature_names,
        train_data_end=payload.train_data_end,
        is_active=False,
    )
    db.add(version)
    db.flush()

    if payload.activate:
        _activate(db, version)

    audit.record(
        db,
        user_id=user.id,
        action="register",
        entity="model_version",
        entity_id=version.id,
        after={
            "commodity_id": payload.commodity_id,
            "horizon": payload.horizon,
            "algorithm": payload.algorithm,
            "artifact_path": payload.artifact_path,
        },
    )
    db.commit()
    return {"status": "registered", "id": version.id, "is_active": version.is_active}


def _activate(db: Session, version: ModelVersion) -> None:
    """Aktifkan satu versi; hanya satu yang boleh aktif per (komoditas, horizon)."""
    siblings = db.execute(
        select(ModelVersion).where(
            ModelVersion.commodity_id == version.commodity_id,
            ModelVersion.horizon == version.horizon,
        )
    ).scalars().all()
    for sibling in siblings:
        sibling.is_active = sibling.id == version.id

    from ..ml.artifacts import clear_model_cache

    clear_model_cache()


@router.post("/models/{model_id}/activate")
def activate_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    version = db.get(ModelVersion, model_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Versi model tidak ditemukan.")
    _activate(db, version)
    audit.record(db, user_id=user.id, action="activate", entity="model_version", entity_id=version.id)
    db.commit()
    return {"status": "activated", "id": version.id}


@router.post("/models/metrics")
def add_metric(
    payload: ModelMetricRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    version = db.get(ModelVersion, payload.model_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Versi model tidak ditemukan.")

    metric = ModelMetric(
        model_version_id=payload.model_version_id,
        split_type=payload.split_type,
        mae=payload.mae,
        rmse=payload.rmse,
        r2=payload.r2,
        mape=payload.mape,
        n_samples=payload.n_samples,
    )
    db.add(metric)
    audit.record(db, user_id=user.id, action="create", entity="model_metric", entity_id=version.id)
    db.commit()
    return {"status": "created", "id": metric.id}


# ---------------------------------------------------------------------------
# Konfigurasi EWS
# ---------------------------------------------------------------------------


@router.get("/ews/settings")
def get_ews_settings(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(EwsSetting)).scalars().all()
    commodities = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    return {
        "global": next(
            (
                {
                    "threshold_waspada": r.threshold_waspada,
                    "threshold_warning": r.threshold_warning,
                    "threshold_kritis": r.threshold_kritis,
                }
                for r in rows
                if r.commodity_id is None
            ),
            None,
        ),
        "overrides": [
            {
                "commodity_id": r.commodity_id,
                "threshold_waspada": r.threshold_waspada,
                "threshold_warning": r.threshold_warning,
                "threshold_kritis": r.threshold_kritis,
            }
            for r in rows
            if r.commodity_id is not None
        ],
        "commodities": [serialize_commodity(c) for c in commodities],
    }


@router.put("/ews/settings")
def update_ews_settings(
    payload: EwsSettingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    setting = db.execute(
        select(EwsSetting).where(
            EwsSetting.commodity_id.is_(None)
            if payload.commodity_id is None
            else EwsSetting.commodity_id == payload.commodity_id
        )
    ).scalars().first()

    before = (
        None
        if setting is None
        else {
            "threshold_waspada": setting.threshold_waspada,
            "threshold_warning": setting.threshold_warning,
            "threshold_kritis": setting.threshold_kritis,
        }
    )

    if setting is None:
        setting = EwsSetting(commodity_id=payload.commodity_id)
        db.add(setting)

    setting.threshold_waspada = payload.threshold_waspada
    setting.threshold_warning = payload.threshold_warning
    setting.threshold_kritis = payload.threshold_kritis
    setting.updated_by = user.id

    audit.record(
        db,
        user_id=user.id,
        action="update",
        entity="ews_setting",
        entity_id=payload.commodity_id,
        before=before,
        after={
            "threshold_waspada": payload.threshold_waspada,
            "threshold_warning": payload.threshold_warning,
            "threshold_kritis": payload.threshold_kritis,
        },
    )

    ews_service.rebuild_alerts(db)
    db.commit()
    return {"status": "updated"}


@router.post("/ews/preview")
def preview_ews(payload: EwsPreviewRequest, db: Session = Depends(get_db)) -> dict:
    return ews_service.preview_threshold_impact(
        db,
        {
            "threshold_waspada": payload.threshold_waspada,
            "threshold_warning": payload.threshold_warning,
            "threshold_kritis": payload.threshold_kritis,
        },
        payload.commodity_id,
    )


@router.delete("/ews/settings/{commodity_id}")
def delete_override(
    commodity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    setting = db.execute(
        select(EwsSetting).where(EwsSetting.commodity_id == commodity_id)
    ).scalars().first()
    if setting is None:
        raise HTTPException(status_code=404, detail="Override tidak ditemukan.")
    db.delete(setting)
    audit.record(db, user_id=user.id, action="delete", entity="ews_setting", entity_id=commodity_id)
    ews_service.rebuild_alerts(db)
    db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Log audit
# ---------------------------------------------------------------------------


@router.get("/audit-logs")
def audit_logs(
    limit: int = Query(default=100, le=500),
    entity: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    rows = db.execute(stmt).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_name": r.user.name if r.user else None,
                "action": r.action,
                "entity": r.entity,
                "entity_id": r.entity_id,
                "before_value": r.before_value,
                "after_value": r.after_value,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }
