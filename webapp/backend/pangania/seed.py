"""Pengisian data awal.

Memuat DATASET-BERAS.csv ke basis data dengan perlakuan yang SAMA dengan
penelitian (workflow step 2): tanggal tanpa survei pasar DIISI lewat
interpolasi berbasis waktu — bukan dibuang — supaya jarak antarbaris tetap
seragam dan fitur lag/rolling tidak rusak. Baris hasil pengisian ditandai
`is_interpolated=True` sehingga tetap dapat dibedakan di antarmuka.

Jalankan:
    python -m pangania.seed
    python -m pangania.seed --reset
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import pandas as pd
from sqlalchemy import func, select

from .config import (
    COMMODITIES,
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_NAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_EWS_THRESHOLDS,
    MODEL_PRICE_SCALE,
    RAW_DATASET_PATH,
)
from .db import Base, SessionLocal, engine
from .models import Commodity, EwsSetting, Price, User
from .security import hash_password
from .services import ews as ews_service
from .services import projections as projection_service

logger = logging.getLogger("pangania.seed")


def seed_commodities(db) -> dict[str, Commodity]:
    existing = {c.name: c for c in db.execute(select(Commodity)).scalars()}
    for order, spec in enumerate(COMMODITIES):
        commodity = existing.get(spec["name"])
        if commodity is None:
            commodity = Commodity(
                code=spec["code"],
                name=spec["name"],
                family=spec["family"],
                unit="Rp/kg",
                display_order=order,
                color_slot=spec["color_slot"],
            )
            db.add(commodity)
            existing[spec["name"]] = commodity
        else:
            commodity.code = spec["code"]
            commodity.family = spec["family"]
            commodity.display_order = order
            commodity.color_slot = spec["color_slot"]
    db.flush()
    return existing


def seed_admin(db) -> User:
    user = db.execute(select(User).where(User.email == DEFAULT_ADMIN_EMAIL)).scalars().first()
    if user is None:
        user = User(
            email=DEFAULT_ADMIN_EMAIL.lower(),
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            name=DEFAULT_ADMIN_NAME,
            role="admin",
        )
        db.add(user)
        db.flush()
        logger.info("Akun admin dibuat: %s", DEFAULT_ADMIN_EMAIL)
    return user


def seed_ews_settings(db) -> None:
    existing = db.execute(select(EwsSetting).where(EwsSetting.commodity_id.is_(None))).scalars().first()
    if existing is None:
        db.add(EwsSetting(commodity_id=None, **DEFAULT_EWS_THRESHOLDS))
        db.flush()


def load_dataset() -> pd.DataFrame:
    if not RAW_DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset tidak ditemukan: {RAW_DATASET_PATH}")

    frame = pd.read_csv(RAW_DATASET_PATH)
    frame["tanggal"] = pd.to_datetime(frame["tanggal"])
    frame = frame.set_index("tanggal").sort_index()

    # Indeks harian kontinu — dataset sudah memuat seluruh tanggal kalender,
    # tapi reindex membuat asumsi ini eksplisit alih-alih tersirat.
    frame = frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq="D"))
    return frame


def seed_prices(db, commodities: dict[str, Commodity], user: User) -> int:
    frame = load_dataset()
    missing_mask = frame.isna()
    filled = frame.interpolate(method="time", limit_direction="both", axis=0)

    already = db.execute(select(func.count(Price.id))).scalar_one()
    if already:
        logger.info("Tabel harga sudah berisi %s baris — pengisian dilewati.", already)
        return 0

    records: list[Price] = []
    for name, commodity in commodities.items():
        if name not in filled.columns:
            logger.warning("Kolom '%s' tidak ada di dataset — dilewati.", name)
            continue

        column = filled[name]
        flags = missing_mask[name]
        for timestamp, value in column.items():
            if pd.isna(value):
                continue
            interpolated = bool(flags.loc[timestamp])
            records.append(
                Price(
                    commodity_id=commodity.id,
                    price_date=timestamp.date(),
                    # Dataset memakai satuan ribu rupiah; basis data memakai
                    # rupiah penuh (lihat config.MODEL_PRICE_SCALE).
                    price=round(float(value) * MODEL_PRICE_SCALE, 2),
                    source="interpolated" if interpolated else "pihps",
                    is_interpolated=interpolated,
                    created_by=user.id,
                )
            )

    db.bulk_save_objects(records)
    db.flush()
    logger.info("Menyimpan %s baris harga.", len(records))
    return len(records)


def reset_database() -> None:
    logger.warning("Menghapus seluruh tabel dan membuat ulang.")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def run(reset: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    if reset:
        reset_database()
    else:
        Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        commodities = seed_commodities(db)
        user = seed_admin(db)
        seed_ews_settings(db)
        inserted = seed_prices(db, commodities, user)
        db.commit()

        if inserted:
            logger.info("Menghitung EWS bulanan...")
            ews_service.rebuild_alerts(db)
            logger.info("Menghitung proyeksi laju kenaikan...")
            projection_service.rebuild_projections(db)
            db.commit()

        total = db.execute(select(func.count(Price.id))).scalar_one()
        last = db.execute(select(func.max(Price.price_date))).scalar_one()

    print("\n== Seed selesai ==")
    print(f"  Komoditas       : {len(COMMODITIES)}")
    print(f"  Baris harga     : {total}")
    print(f"  Data terakhir   : {last}")
    print(f"  Login admin     : {DEFAULT_ADMIN_EMAIL} / {DEFAULT_ADMIN_PASSWORD}")
    print("\n  Catatan: model prediksi belum terdaftar, jadi kartu prediksi akan")
    print("  menampilkan status 'belum tersedia' sampai artefak .pkl didaftarkan.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Isi basis data PANGANIA.")
    parser.add_argument("--reset", action="store_true", help="Hapus dan buat ulang seluruh tabel.")
    args = parser.parse_args()
    run(reset=args.reset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
