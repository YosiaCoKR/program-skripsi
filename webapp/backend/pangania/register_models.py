"""Pendaftaran artefak model secara massal.

Dipakai setelah 27 model (9 komoditas x 3 horizon) selesai dilatih di notebook.
Skrip memindai `backend/artifacts/models/`, mencocokkan nama berkas dengan
komoditas dan horizon, lalu mendaftarkannya ke tabel `model_versions`.

KONVENSI NAMA BERKAS
--------------------
    {algoritma}__{kode_komoditas}__h{horizon}.pkl

Contoh:
    ga_lightgbm__cabai-rawit-merah__h1.pkl
    ga_lightgbm__beras-medium-1__h30.pkl

Kode komoditas mengikuti kolom `code` pada tabel commodities — lihat daftar
lengkapnya dengan `--list-codes`.

MENYERTAKAN METRIK
------------------
Bila ada berkas JSON bernama sama (berekstensi .json), isinya dibaca sebagai
metadata:

    {
      "hyperparameters": {"num_leaves": 64, ...},
      "feature_names": ["...", "..."],
      "train_data_end": "2026-08-03",
      "metrics": {"mae": 120.5, "rmse": 180.2, "r2": 0.87, "mape": 1.4,
                  "split_type": "walk_forward", "n_samples": 400}
    }

Contoh pemakaian:
    python -m pangania.register_models --dry-run
    python -m pangania.register_models
    python -m pangania.register_models --algorithm lightgbm_default --no-activate
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from .config import HORIZONS, MODEL_DIR
from .db import Base, SessionLocal, engine
from .models import Commodity, ModelMetric, ModelVersion

logger = logging.getLogger("pangania.register_models")

FILENAME_PATTERN = re.compile(r"^(?P<algorithm>.+?)__(?P<code>.+?)__h(?P<horizon>\d+)\.pkl$")


def parse_filename(name: str) -> tuple[str, str, int] | None:
    match = FILENAME_PATTERN.match(name)
    if not match:
        return None
    horizon = int(match.group("horizon"))
    if horizon not in HORIZONS:
        return None
    return match.group("algorithm"), match.group("code"), horizon


def load_sidecar(path: Path) -> dict:
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return {}
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Metadata %s diabaikan: %s", sidecar.name, exc)
        return {}


def activate(db, version: ModelVersion) -> None:
    siblings = db.execute(
        select(ModelVersion).where(
            ModelVersion.commodity_id == version.commodity_id,
            ModelVersion.horizon == version.horizon,
        )
    ).scalars().all()
    for sibling in siblings:
        sibling.is_active = sibling.id == version.id


def run(dry_run: bool, force_algorithm: str | None, do_activate: bool) -> int:
    Base.metadata.create_all(bind=engine)

    files = sorted(MODEL_DIR.glob("*.pkl"))
    if not files:
        print(f"Tidak ada berkas .pkl di {MODEL_DIR}")
        print("Salin artefak model hasil notebook ke direktori tersebut lebih dulu.")
        return 1

    registered = skipped = 0

    with SessionLocal() as db:
        commodities = {c.code: c for c in db.execute(select(Commodity)).scalars()}
        if not commodities:
            print("Tabel commodities kosong. Jalankan `python -m pangania.seed` lebih dulu.")
            return 1

        for path in files:
            parsed = parse_filename(path.name)
            if parsed is None:
                logger.warning("Nama berkas tidak sesuai konvensi, dilewati: %s", path.name)
                skipped += 1
                continue

            algorithm, code, horizon = parsed
            commodity = commodities.get(code)
            if commodity is None:
                logger.warning("Kode komoditas '%s' tidak dikenal (%s)", code, path.name)
                skipped += 1
                continue

            meta = load_sidecar(path)
            train_end = meta.get("train_data_end")

            print(
                f"  {'[dry-run] ' if dry_run else ''}{commodity.name} H+{horizon} "
                f"<- {path.name} ({force_algorithm or algorithm})"
            )
            if dry_run:
                registered += 1
                continue

            version = ModelVersion(
                commodity_id=commodity.id,
                horizon=horizon,
                algorithm=force_algorithm or algorithm,
                label=f"{force_algorithm or algorithm} {commodity.code} H+{horizon}",
                artifact_path=path.name,
                hyperparameters=meta.get("hyperparameters", {}),
                feature_names=meta.get("feature_names", []),
                train_data_end=date.fromisoformat(train_end) if train_end else None,
                is_active=False,
            )
            db.add(version)
            db.flush()

            metrics = meta.get("metrics")
            if isinstance(metrics, dict):
                db.add(
                    ModelMetric(
                        model_version_id=version.id,
                        split_type=metrics.get("split_type", "walk_forward"),
                        mae=metrics.get("mae"),
                        rmse=metrics.get("rmse"),
                        r2=metrics.get("r2"),
                        mape=metrics.get("mape"),
                        n_samples=metrics.get("n_samples"),
                    )
                )

            if do_activate:
                activate(db, version)

            registered += 1

        if not dry_run:
            db.commit()

        active_count = db.execute(
            select(ModelVersion).where(ModelVersion.is_active.is_(True))
        ).scalars().all()

    print()
    print(f"Terdaftar : {registered}")
    print(f"Dilewati  : {skipped}")
    if not dry_run:
        print(f"Aktif     : {len(active_count)} dari {len(HORIZONS) * 9} yang diharapkan")
        print()
        print("Jalankan forecast dari panel admin (Monitor Rolling Forecast) untuk")
        print("menghasilkan prediksi pertama.")
    return 0


def list_codes() -> int:
    with SessionLocal() as db:
        rows = db.execute(select(Commodity).order_by(Commodity.display_order)).scalars().all()
    if not rows:
        print("Tabel commodities kosong. Jalankan `python -m pangania.seed` lebih dulu.")
        return 1
    print("Kode komoditas yang dikenal:\n")
    for row in rows:
        print(f"  {row.code:<24} {row.name}")
    print("\nContoh nama berkas: ga_lightgbm__%s__h7.pkl" % rows[0].code)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    parser = argparse.ArgumentParser(description="Daftarkan artefak model ke basis data.")
    parser.add_argument("--dry-run", action="store_true", help="Tampilkan rencana tanpa menyimpan.")
    parser.add_argument("--algorithm", default=None, help="Paksa nama algoritma untuk semua berkas.")
    parser.add_argument("--no-activate", action="store_true", help="Daftarkan tanpa mengaktifkan.")
    parser.add_argument("--list-codes", action="store_true", help="Tampilkan kode komoditas.")
    args = parser.parse_args()

    if args.list_codes:
        return list_codes()

    print(f"Memindai {MODEL_DIR}\n")
    return run(args.dry_run, args.algorithm, not args.no_activate)


if __name__ == "__main__":
    sys.exit(main())
