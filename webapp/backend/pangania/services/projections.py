"""Proyeksi laju kenaikan 2-3 tahun (workflow step 11).

BUKAN keluaran LightGBM. Proyeksi jangka panjang memakai dua hal:

* CAGR historis  — laju pertumbuhan majemuk dari data aktual.
* Ekstrapolasi trend — `trend_models.pkl` (LinearRegression di atas trend MSTL).

Disclaimer ini wajib ikut tampil di antarmuka (PRD fitur #6): memaksa LightGBM
memprediksi nilai eksak untuk horizon tahunan adalah kesalahan metodologis.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MODEL_PRICE_SCALE
from ..models import Commodity, Price, Projection
from ..ml.artifacts import ArtifactMissingError
from ..ml.decomposition import get_decomposition

logger = logging.getLogger(__name__)

DAYS_PER_YEAR = 365
PROJECTION_YEARS = (2, 3)

# Rentang ketidakpastian proyeksi dinyatakan sebagai persentase dari nilai
# proyeksi. Nilainya melebar seiring horizon karena ekstrapolasi linear makin
# jauh dari rentang data yang pernah dilihat model (trend extrapolation drift).
UNCERTAINTY_PCT_PER_YEAR = 0.06


def compute_projection(db: Session, commodity: Commodity, years: int) -> dict | None:
    rows = db.execute(
        select(Price.price_date, Price.price)
        .where(Price.commodity_id == commodity.id)
        .order_by(Price.price_date)
    ).all()
    if len(rows) < 2:
        return None

    first_date, first_price = rows[0].price_date, float(rows[0].price)
    last_date, last_price = rows[-1].price_date, float(rows[-1].price)

    span_years = (last_date - first_date).days / DAYS_PER_YEAR
    if span_years <= 0 or first_price <= 0:
        return None

    cagr = (last_price / first_price) ** (1 / span_years) - 1

    target_date = last_date + timedelta(days=DAYS_PER_YEAR * years)

    # Ekstrapolasi trend MSTL lewat model linear (step 4). Kalau artefak belum
    # tersedia, jatuh ke proyeksi berbasis CAGR saja.
    try:
        decomposition = get_decomposition(commodity.name)
        projected_price = decomposition.trend_at(target_date) * MODEL_PRICE_SCALE
        method = "trend_extrapolation"
    except (ArtifactMissingError, KeyError) as exc:
        logger.warning("Trend model tidak tersedia untuk %s: %s", commodity.name, exc)
        projected_price = last_price * ((1 + cagr) ** years)
        method = "cagr_only"

    margin = projected_price * UNCERTAINTY_PCT_PER_YEAR * years

    return {
        "horizon_years": years,
        "cagr": cagr * 100.0,
        "base_price": last_price,
        "base_date": last_date,
        "target_date": target_date,
        "projected_price": projected_price,
        "lower_bound": projected_price - margin,
        "upper_bound": projected_price + margin,
        "total_growth_pct": (projected_price / last_price - 1) * 100.0 if last_price else None,
        "method": method,
    }


def rebuild_projections(db: Session) -> int:
    commodities = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    written = 0

    for commodity in commodities:
        for years in PROJECTION_YEARS:
            payload = compute_projection(db, commodity, years)
            if payload is None:
                continue

            existing = db.execute(
                select(Projection).where(
                    Projection.commodity_id == commodity.id,
                    Projection.horizon_years == years,
                )
            ).scalars().first()
            if existing is None:
                existing = Projection(commodity_id=commodity.id, horizon_years=years)
                db.add(existing)

            existing.cagr = payload["cagr"]
            existing.base_price = payload["base_price"]
            existing.projected_price = payload["projected_price"]
            existing.lower_bound = payload["lower_bound"]
            existing.upper_bound = payload["upper_bound"]
            written += 1

    db.flush()
    return written
