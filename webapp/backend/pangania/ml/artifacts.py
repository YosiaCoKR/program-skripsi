"""Pemuatan artefak hasil penelitian.

Artefak bersifat READ-ONLY bagi aplikasi (PRD §5 catatan arsitektur #2).
Aplikasi memuat objek yang sama persis dengan yang dipakai saat training —
tidak pernah me-refit, tidak pernah menulis ulang logika `shift()`/`rolling()`.
"""

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import (
    FEATURE_TRANSFORMERS_PATH,
    MODEL_DIR,
    STL_RESULTS_PATH,
    TREND_MODELS_PATH,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class ArtifactMissingError(RuntimeError):
    """Artefak penelitian tidak ditemukan atau gagal dimuat."""


def _load_pickle(path: Path, label: str) -> Any:
    import joblib

    if not path.exists():
        raise ArtifactMissingError(
            f"Artefak {label} tidak ditemukan di {path}. "
            "Jalankan notebook penelitian sampai step yang menghasilkannya."
        )
    try:
        return joblib.load(path)
    except Exception as exc:  # pragma: no cover - bergantung lingkungan
        raise ArtifactMissingError(f"Gagal memuat artefak {label} dari {path}: {exc}") from exc


@lru_cache(maxsize=1)
def load_trend_models() -> dict[str, Any]:
    """`{nama_komoditas: LinearRegression}` — di-fit di atas trend MSTL (step 4)."""
    return _load_pickle(TREND_MODELS_PATH, "trend_models.pkl")


@lru_cache(maxsize=1)
def load_feature_transformers() -> dict[str, dict[str, Any]]:
    """`{nama_komoditas: {'lags': LagFeatures, 'window': WindowFeatures}}` (step 5)."""
    return _load_pickle(FEATURE_TRANSFORMERS_PATH, "features_transformers.pkl")


@lru_cache(maxsize=1)
def load_stl_results() -> dict[str, Any]:
    """`{nama_komoditas: MSTLResults}` — sumber komponen trend & seasonal (step 4)."""
    return _load_pickle(STL_RESULTS_PATH, "stl_results.pkl")


def artifact_status() -> dict[str, dict[str, Any]]:
    """Status ketersediaan tiap artefak, untuk ditampilkan di dashboard admin."""
    result: dict[str, dict[str, Any]] = {}
    for label, path, loader in (
        ("trend_models", TREND_MODELS_PATH, load_trend_models),
        ("features_transformers", FEATURE_TRANSFORMERS_PATH, load_feature_transformers),
        ("stl_results", STL_RESULTS_PATH, load_stl_results),
    ):
        entry: dict[str, Any] = {"path": str(path), "exists": path.exists()}
        if path.exists():
            try:
                obj = loader()
                entry["loaded"] = True
                entry["n_commodities"] = len(obj) if hasattr(obj, "__len__") else None
            except ArtifactMissingError as exc:
                entry["loaded"] = False
                entry["error"] = str(exc)
        else:
            entry["loaded"] = False
        result[label] = entry
    return result


# ---------------------------------------------------------------------------
# Artefak model prediksi (LightGBM) — dikelola aplikasi, satu berkas per
# kombinasi komoditas x horizon, dirujuk lewat tabel model_versions.
# ---------------------------------------------------------------------------

_model_cache: dict[str, Any] = {}


def load_prediction_model(artifact_path: str) -> Any:
    """Muat model prediksi dengan cache proses.

    Cache dikunci pada path relatif sehingga mengaktifkan versi model baru
    (path berbeda) otomatis melewati cache lama.
    """
    with _lock:
        if artifact_path in _model_cache:
            return _model_cache[artifact_path]

    path = Path(artifact_path)
    if not path.is_absolute():
        path = MODEL_DIR / artifact_path
    model = _load_pickle(path, f"model {artifact_path}")

    with _lock:
        _model_cache[artifact_path] = model
    return model


def clear_model_cache() -> None:
    with _lock:
        _model_cache.clear()
