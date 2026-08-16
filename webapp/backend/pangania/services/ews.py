"""Early Warning System bulanan (workflow step 12).

Logika lengkapnya membandingkan PREDIKSI H+30 dengan REALISASI AKTUAL, bukan
sekadar mendeteksi anomali statistik dari data aktual saja:

1. Agregasi harga aktual harian menjadi rata-rata bulanan.
2. `actual_pct_mom`    = perubahan bulanan realisasi.
3. `predicted_pct_mom` = perubahan bulanan dari prediksi H+30.
4. `deviation`         = realisasi - prediksi (komponen "prediksi vs realisasi").
5. `z_score`           = (actual_pct_mom - mean historis) / std historis.
6. Level alert ditentukan ambang batas yang DAPAT DIKONFIGURASI admin.

Kalau belum ada prediksi H+30 tersimpan (model masih dikerjakan), kolom
prediksi dan deviasi bernilai None — z-score tetap dihitung dari realisasi
sehingga panel EWS tetap informatif, dan antarmuka menandai bahwa komponen
perbandingan prediksi belum tersedia.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DEFAULT_EWS_THRESHOLDS
from ..models import Commodity, EwsAlert, EwsSetting, Prediction, Price

LEVELS = ("normal", "waspada", "warning", "kritis")

LEVEL_LABELS = {
    "normal": "Normal",
    "waspada": "Waspada",
    "warning": "Warning",
    "kritis": "Kritis",
    "tidak_tersedia": "Tidak tersedia",
}


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def resolve_thresholds(db: Session, commodity_id: int) -> dict[str, float]:
    """Ambang batas efektif: override per komoditas, jatuh ke global, lalu bawaan."""
    specific = db.execute(
        select(EwsSetting).where(EwsSetting.commodity_id == commodity_id)
    ).scalars().first()
    if specific is not None:
        return {
            "threshold_waspada": specific.threshold_waspada,
            "threshold_warning": specific.threshold_warning,
            "threshold_kritis": specific.threshold_kritis,
        }

    global_setting = db.execute(
        select(EwsSetting).where(EwsSetting.commodity_id.is_(None))
    ).scalars().first()
    if global_setting is not None:
        return {
            "threshold_waspada": global_setting.threshold_waspada,
            "threshold_warning": global_setting.threshold_warning,
            "threshold_kritis": global_setting.threshold_kritis,
        }

    return dict(DEFAULT_EWS_THRESHOLDS)


def classify(z_score: float | None, thresholds: dict[str, float]) -> str:
    if z_score is None:
        return "tidak_tersedia"
    if z_score > thresholds["threshold_kritis"]:
        return "kritis"
    if z_score > thresholds["threshold_warning"]:
        return "warning"
    if z_score > thresholds["threshold_waspada"]:
        return "waspada"
    return "normal"


def _monthly_mean(pairs: list[tuple[date, float]]) -> dict[date, float]:
    buckets: dict[date, list[float]] = defaultdict(list)
    for day, value in pairs:
        buckets[_month_start(day)].append(value)
    return {month: sum(values) / len(values) for month, values in buckets.items()}


def _pct_change(series: dict[date, float]) -> dict[date, float]:
    months = sorted(series)
    result: dict[date, float] = {}
    for previous, current in zip(months, months[1:]):
        base = series[previous]
        if base:
            result[current] = (series[current] - base) / base * 100.0
    return result


def _mean_std(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return (values[0] if values else 0.0), 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return mean, variance**0.5


def compute_ews_rows(db: Session, commodity: Commodity) -> list[dict]:
    """Hitung baris EWS bulanan untuk satu komoditas (tanpa menyimpan)."""
    price_rows = db.execute(
        select(Price.price_date, Price.price)
        .where(Price.commodity_id == commodity.id)
        .order_by(Price.price_date)
    ).all()
    if not price_rows:
        return []

    actual_monthly = _monthly_mean([(r.price_date, float(r.price)) for r in price_rows])
    actual_pct = _pct_change(actual_monthly)

    prediction_rows = db.execute(
        select(Prediction.target_date, Prediction.predicted_price)
        .where(Prediction.commodity_id == commodity.id, Prediction.horizon == 30)
        .order_by(Prediction.target_date)
    ).all()
    predicted_monthly = _monthly_mean(
        [(r.target_date, float(r.predicted_price)) for r in prediction_rows]
    )
    predicted_pct = _pct_change(predicted_monthly)

    history = list(actual_pct.values())
    mean_hist, std_hist = _mean_std(history)

    thresholds = resolve_thresholds(db, commodity.id)

    rows: list[dict] = []
    for month in sorted(actual_pct):
        actual_change = actual_pct[month]
        predicted_change = predicted_pct.get(month)
        deviation = None if predicted_change is None else actual_change - predicted_change
        z_score = (actual_change - mean_hist) / std_hist if std_hist > 0 else None

        rows.append(
            {
                "period_month": month,
                "actual_pct_mom": actual_change,
                "predicted_pct_mom": predicted_change,
                "deviation": deviation,
                "z_score": z_score,
                "level": classify(z_score, thresholds),
                "has_prediction": predicted_change is not None,
            }
        )
    return rows


def rebuild_alerts(db: Session, commodity_ids: list[int] | None = None) -> int:
    """Hitung ulang dan simpan snapshot EWS."""
    stmt = select(Commodity).order_by(Commodity.display_order)
    if commodity_ids:
        stmt = stmt.where(Commodity.id.in_(commodity_ids))
    commodities = db.execute(stmt).scalars().all()

    written = 0
    for commodity in commodities:
        existing = {
            alert.period_month: alert
            for alert in db.execute(
                select(EwsAlert).where(EwsAlert.commodity_id == commodity.id)
            ).scalars()
        }
        for row in compute_ews_rows(db, commodity):
            alert = existing.get(row["period_month"])
            if alert is None:
                alert = EwsAlert(commodity_id=commodity.id, period_month=row["period_month"])
                db.add(alert)
            alert.actual_pct_mom = row["actual_pct_mom"]
            alert.predicted_pct_mom = row["predicted_pct_mom"]
            alert.deviation = row["deviation"]
            alert.z_score = row["z_score"]
            alert.level = row["level"]
            written += 1

    db.flush()
    return written


def preview_threshold_impact(
    db: Session, thresholds: dict[str, float], commodity_id: int | None = None
) -> dict:
    """Berapa banyak alert historis berubah level dengan ambang baru.

    Mendukung fitur "pratinjau dampak" di PRD fitur #12 — admin melihat efeknya
    sebelum menyimpan.
    """
    stmt = select(EwsAlert)
    if commodity_id is not None:
        stmt = stmt.where(EwsAlert.commodity_id == commodity_id)
    alerts = db.execute(stmt).scalars().all()

    before: dict[str, int] = {level: 0 for level in (*LEVELS, "tidak_tersedia")}
    after: dict[str, int] = {level: 0 for level in (*LEVELS, "tidak_tersedia")}
    changed = 0

    for alert in alerts:
        new_level = classify(alert.z_score, thresholds)
        before[alert.level] = before.get(alert.level, 0) + 1
        after[new_level] = after.get(new_level, 0) + 1
        if new_level != alert.level:
            changed += 1

    return {"total": len(alerts), "changed": changed, "before": before, "after": after}
