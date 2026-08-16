"""Model ORM — implementasi ERD di PRD §6."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Commodity(Base):
    __tablename__ = "commodities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # `name` harus identik dengan nama kolom di DATASET-BERAS.csv karena dipakai
    # sebagai kunci ke artefak model (trend_models / features_transformers).
    name: Mapped[str] = mapped_column(String(128), unique=True)
    family: Mapped[str] = mapped_column(String(64), index=True)
    unit: Mapped[str] = mapped_column(String(32), default="Rp/kg")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    color_slot: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    prices: Mapped[list["Price"]] = relationship(back_populates="commodity")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Price(Base):
    """Harga AKTUAL harian.

    Tabel ini adalah satu-satunya sumber kebenaran untuk pembentukan fitur
    lag/rolling. Hasil prediksi tidak pernah masuk ke sini — inilah yang
    memisahkan Rolling One-Step Forecast dari Recursive Forecasting.

    `price` disimpan dalam RUPIAH PENUH (mis. 10400), bukan skala model.
    """

    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("commodity_id", "price_date", name="uq_price_commodity_date"),
        Index("ix_price_date_commodity", "price_date", "commodity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"), index=True)
    price_date: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[float] = mapped_column(Float)
    # 'pihps' | 'manual' | 'interpolated'
    source: Mapped[str] = mapped_column(String(32), default="manual")
    is_interpolated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    commodity: Mapped[Commodity] = relationship(back_populates="prices")


class ModelVersion(Base):
    """Registri artefak model per komoditas x horizon.

    Hanya satu versi yang boleh `is_active` untuk tiap pasangan
    (commodity_id, horizon).
    """

    __tablename__ = "model_versions"
    __table_args__ = (Index("ix_modelversion_lookup", "commodity_id", "horizon", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"), index=True)
    horizon: Mapped[int] = mapped_column(Integer, index=True)
    # 'ga_lightgbm' | 'lightgbm_default' | 'lightgbm_grid' | 'naive'
    algorithm: Mapped[str] = mapped_column(String(64), default="lightgbm_default")
    label: Mapped[str] = mapped_column(String(128), default="")
    hyperparameters: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    feature_names: Mapped[list] = mapped_column(JSON, default=list)
    train_data_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    commodity: Mapped[Commodity] = relationship()
    metrics: Mapped[list["ModelMetric"]] = relationship(back_populates="model_version", cascade="all, delete-orphan")


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id", ondelete="CASCADE"), index=True)
    # 'walk_forward' | 'kfold_ga'
    split_type: Mapped[str] = mapped_column(String(32), default="walk_forward")
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    r2: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_samples: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    model_version: Mapped[ModelVersion] = relationship(back_populates="metrics")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_date: Mapped[date] = mapped_column(Date, index=True)
    # 'pending' | 'success' | 'failed' | 'partial'
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # 'price_input' | 'price_correction' | 'manual_rerun' | 'seed'
    trigger_type: Mapped[str] = mapped_column(String(32), default="price_input")
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    predictions_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Prediction(Base):
    """Hasil prediksi.

    `predicted_residual`, `trend_component`, dan `seasonal_component` disimpan
    terpisah supaya rekonstruksi harga bisa ditelusuri dan diverifikasi ulang:
    predicted_price = predicted_residual + trend_component + seasonal_component
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("commodity_id", "horizon", "base_date", name="uq_prediction_slot"),
        Index("ix_prediction_target", "commodity_id", "target_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"), index=True)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"), nullable=True)
    forecast_run_id: Mapped[int | None] = mapped_column(ForeignKey("forecast_runs.id"), nullable=True)
    horizon: Mapped[int] = mapped_column(Integer, index=True)
    base_date: Mapped[date] = mapped_column(Date, index=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    predicted_price: Mapped[float] = mapped_column(Float)
    predicted_residual: Mapped[float] = mapped_column(Float)
    trend_component: Mapped[float] = mapped_column(Float)
    seasonal_component: Mapped[float] = mapped_column(Float, default=0.0)
    lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    commodity: Mapped[Commodity] = relationship()
    model_version: Mapped[ModelVersion | None] = relationship()


class EwsSetting(Base):
    """Ambang batas EWS.

    `commodity_id` NULL berarti pengaturan global; baris dengan commodity_id
    terisi meng-override global untuk komoditas tersebut.
    """

    __tablename__ = "ews_settings"
    __table_args__ = (UniqueConstraint("commodity_id", name="uq_ews_setting_commodity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int | None] = mapped_column(ForeignKey("commodities.id"), nullable=True)
    threshold_waspada: Mapped[float] = mapped_column(Float, default=1.0)
    threshold_warning: Mapped[float] = mapped_column(Float, default=1.5)
    threshold_kritis: Mapped[float] = mapped_column(Float, default=2.0)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    commodity: Mapped[Commodity | None] = relationship()


class EwsAlert(Base):
    __tablename__ = "ews_alerts"
    __table_args__ = (UniqueConstraint("commodity_id", "period_month", name="uq_ews_alert_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"), index=True)
    period_month: Mapped[date] = mapped_column(Date, index=True)  # selalu tanggal 1
    actual_pct_mom: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_pct_mom: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation: Mapped[float | None] = mapped_column(Float, nullable=True)
    z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 'normal' | 'waspada' | 'warning' | 'kritis' | 'tidak_tersedia'
    level: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    commodity: Mapped[Commodity] = relationship()


class Projection(Base):
    __tablename__ = "projections"
    __table_args__ = (UniqueConstraint("commodity_id", "horizon_years", name="uq_projection_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"), index=True)
    horizon_years: Mapped[int] = mapped_column(Integer)
    cagr: Mapped[float] = mapped_column(Float)
    base_price: Mapped[float] = mapped_column(Float)
    projected_price: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    commodity: Mapped[Commodity] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    user: Mapped[User | None] = relationship()
