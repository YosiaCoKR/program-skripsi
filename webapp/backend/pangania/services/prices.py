"""Aturan bisnis penyimpanan harga aktual.

Menangani tiga hal yang diminta PRD fitur #8:

* Validasi outlier  — lonjakan > 20% MEMPERINGATKAN, tidak memblokir, karena
                      lonjakan cabai memang wajar terjadi.
* Deteksi tanggal bolong — gap kalender antara data terakhir dan tanggal baru.
* Pengisian interpolasi  — gap diisi (bukan dibuang) supaya jarak antarbaris
                      tetap seragam dan fitur lag/rolling tidak rusak.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import OUTLIER_PCT_THRESHOLD
from ..models import Commodity, Price
from . import audit


@dataclass
class OutlierWarning:
    commodity_id: int
    commodity_name: str
    previous_price: float
    new_price: float
    change_pct: float


@dataclass
class SaveResult:
    saved: int = 0
    updated: int = 0
    interpolated: int = 0
    warnings: list[OutlierWarning] = field(default_factory=list)
    gap_dates: list[date] = field(default_factory=list)


def latest_price_date(db: Session, commodity_id: int | None = None) -> date | None:
    stmt = select(func.max(Price.price_date))
    if commodity_id is not None:
        stmt = stmt.where(Price.commodity_id == commodity_id)
    return db.execute(stmt).scalar_one_or_none()


def previous_price(db: Session, commodity_id: int, before: date) -> Price | None:
    return db.execute(
        select(Price)
        .where(Price.commodity_id == commodity_id, Price.price_date < before)
        .order_by(Price.price_date.desc())
        .limit(1)
    ).scalars().first()


def price_on(db: Session, commodity_id: int, day: date) -> Price | None:
    return db.execute(
        select(Price).where(Price.commodity_id == commodity_id, Price.price_date == day)
    ).scalars().first()


def detect_gap(db: Session, target_date: date) -> list[date]:
    """Tanggal antara data terakhir dan `target_date` yang belum punya harga."""
    last = latest_price_date(db)
    if last is None or target_date <= last:
        return []
    return [last + timedelta(days=n) for n in range(1, (target_date - last).days)]


def check_outliers(db: Session, entries: dict[int, float], target_date: date) -> list[OutlierWarning]:
    """Deteksi lonjakan besar dibanding harga sebelumnya."""
    warnings: list[OutlierWarning] = []
    for commodity_id, new_price in entries.items():
        prev = previous_price(db, commodity_id, target_date)
        if prev is None or prev.price <= 0:
            continue
        change_pct = (new_price - prev.price) / prev.price * 100.0
        if abs(change_pct) > OUTLIER_PCT_THRESHOLD:
            commodity = db.get(Commodity, commodity_id)
            warnings.append(
                OutlierWarning(
                    commodity_id=commodity_id,
                    commodity_name=commodity.name if commodity else str(commodity_id),
                    previous_price=float(prev.price),
                    new_price=float(new_price),
                    change_pct=change_pct,
                )
            )
    return warnings


def fill_gap_by_interpolation(
    db: Session,
    commodity_id: int,
    gap_dates: list[date],
    end_date: date,
    end_price: float,
    user_id: int | None,
) -> int:
    """Isi tanggal kosong dengan interpolasi linear berbasis waktu.

    Hasilnya ditandai `is_interpolated=True` supaya bisa dibedakan secara visual
    dari data survei asli di seluruh grafik (PRD §7.6 poin 3).
    """
    if not gap_dates:
        return 0

    start = previous_price(db, commodity_id, gap_dates[0])
    if start is None:
        return 0

    total_days = (end_date - start.price_date).days
    if total_days <= 0:
        return 0

    created = 0
    for day in gap_dates:
        if price_on(db, commodity_id, day) is not None:
            continue
        ratio = (day - start.price_date).days / total_days
        value = start.price + (end_price - start.price) * ratio
        db.add(
            Price(
                commodity_id=commodity_id,
                price_date=day,
                price=round(value, 2),
                source="interpolated",
                is_interpolated=True,
                created_by=user_id,
            )
        )
        created += 1
    return created


def save_daily_prices(
    db: Session,
    *,
    target_date: date,
    entries: dict[int, float],
    user_id: int | None,
    fill_gaps: bool = True,
    source: str = "manual",
) -> SaveResult:
    """Simpan harga 9 komoditas untuk satu tanggal."""
    result = SaveResult()
    result.warnings = check_outliers(db, entries, target_date)
    gap_dates = detect_gap(db, target_date) if fill_gaps else []
    result.gap_dates = gap_dates

    for commodity_id, value in entries.items():
        if fill_gaps and gap_dates:
            result.interpolated += fill_gap_by_interpolation(
                db, commodity_id, gap_dates, target_date, value, user_id
            )

        existing = price_on(db, commodity_id, target_date)
        if existing is None:
            record = Price(
                commodity_id=commodity_id,
                price_date=target_date,
                price=value,
                source=source,
                is_interpolated=False,
                created_by=user_id,
            )
            db.add(record)
            db.flush()
            result.saved += 1
            audit.record(
                db,
                user_id=user_id,
                action="create",
                entity="price",
                entity_id=record.id,
                after={"commodity_id": commodity_id, "price_date": target_date, "price": value},
            )
        else:
            before = {
                "price": float(existing.price),
                "source": existing.source,
                "is_interpolated": existing.is_interpolated,
            }
            existing.price = value
            existing.source = source
            existing.is_interpolated = False
            existing.created_by = user_id
            result.updated += 1
            audit.record(
                db,
                user_id=user_id,
                action="update",
                entity="price",
                entity_id=existing.id,
                before=before,
                after={"price": value, "source": source, "is_interpolated": False},
            )

    db.flush()
    return result
