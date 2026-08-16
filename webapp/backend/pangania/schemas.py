"""Skema request/response (Pydantic v2)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class PriceEntry(BaseModel):
    commodity_id: int
    price: float = Field(gt=0, description="Harga dalam rupiah penuh, mis. 12750")


class DailyPriceRequest(BaseModel):
    price_date: date
    entries: list[PriceEntry] = Field(min_length=1)
    fill_gaps: bool = True
    # Admin sudah melihat peringatan outlier dan tetap ingin menyimpan.
    confirm_outliers: bool = False
    run_forecast: bool = True

    @field_validator("entries")
    @classmethod
    def _unique_commodities(cls, value: list[PriceEntry]) -> list[PriceEntry]:
        seen = {entry.commodity_id for entry in value}
        if len(seen) != len(value):
            raise ValueError("Terdapat commodity_id duplikat dalam satu permintaan")
        return value


class PriceUpdateRequest(BaseModel):
    price: float = Field(gt=0)
    run_forecast: bool = True


class CsvImportRow(BaseModel):
    price_date: date
    values: dict[str, float]


class CsvImportRequest(BaseModel):
    rows: list[CsvImportRow]
    commit: bool = False
    run_forecast: bool = True


class EwsSettingRequest(BaseModel):
    commodity_id: int | None = None
    threshold_waspada: float = Field(gt=0)
    threshold_warning: float = Field(gt=0)
    threshold_kritis: float = Field(gt=0)

    @field_validator("threshold_kritis")
    @classmethod
    def _ordered(cls, value: float, info) -> float:
        data = info.data
        waspada = data.get("threshold_waspada")
        warning = data.get("threshold_warning")
        if waspada is not None and warning is not None and not (waspada < warning < value):
            raise ValueError("Ambang harus menaik: waspada < warning < kritis")
        return value


class EwsPreviewRequest(BaseModel):
    commodity_id: int | None = None
    threshold_waspada: float = Field(gt=0)
    threshold_warning: float = Field(gt=0)
    threshold_kritis: float = Field(gt=0)


class ForecastRunRequest(BaseModel):
    base_date: date | None = None
    commodity_ids: list[int] | None = None


class ModelVersionRequest(BaseModel):
    """Pendaftaran artefak model.

    Dipakai saat artefak GA-LightGBM hasil notebook sudah siap. `artifact_path`
    relatif terhadap direktori `backend/artifacts/models/`.
    """

    commodity_id: int
    horizon: int
    algorithm: str = "ga_lightgbm"
    label: str = ""
    artifact_path: str
    hyperparameters: dict = Field(default_factory=dict)
    feature_names: list[str] = Field(default_factory=list)
    train_data_end: date | None = None
    activate: bool = True

    @field_validator("horizon")
    @classmethod
    def _valid_horizon(cls, value: int) -> int:
        if value not in (1, 7, 30):
            raise ValueError("Horizon harus salah satu dari 1, 7, atau 30")
        return value


class ModelMetricRequest(BaseModel):
    model_version_id: int
    split_type: str = "walk_forward"
    mae: float | None = None
    rmse: float | None = None
    r2: float | None = None
    mape: float | None = None
    n_samples: int | None = None
