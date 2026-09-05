"""Konfigurasi aplikasi yang bisa diubah admin lewat panel (mis. model aktif).

Disimpan di `config.json` (bukan environment variable) karena nilainya
berubah lewat interaksi admin saat aplikasi berjalan, beda dengan
`ADMIN_PASSWORD` yang disetel sekali saat deploy — lihat `auth.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.json"
_DEFAULT_CONFIG = {"model_aktif": None}


def _muat_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as berkas:
                return {**_DEFAULT_CONFIG, **json.load(berkas)}
        except (json.JSONDecodeError, OSError):
            # config.json rusak/kosong (mis. proses server terhenti di tengah
            # penulisan) — jangan sampai seluruh halaman admin ikut error,
            # kembali ke default dan biarkan admin menyimpan ulang pilihannya.
            return dict(_DEFAULT_CONFIG)
    return dict(_DEFAULT_CONFIG)


def _simpan_config(config: dict) -> None:
    # Tulis ke berkas sementara lalu rename (atomik di level filesystem) —
    # supaya config.json tidak pernah dalam keadaan terpotong separuh kalau
    # proses server mati persis saat menulis.
    berkas_sementara = _CONFIG_PATH.with_suffix(".json.tmp")
    with open(berkas_sementara, "w", encoding="utf-8") as berkas:
        json.dump(config, berkas, indent=2)
    berkas_sementara.replace(_CONFIG_PATH)


def get_model_aktif() -> str | None:
    return _muat_config().get("model_aktif")


def set_model_aktif(nama_file: str) -> None:
    config = _muat_config()
    config["model_aktif"] = nama_file
    _simpan_config(config)
