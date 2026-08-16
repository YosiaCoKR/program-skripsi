"""Pencatatan jejak audit.

Kebutuhan akademik (PRD requirement "Auditabilitas"): setiap angka prediksi
harus bisa ditelusuri ke input yang menghasilkannya, jadi seluruh mutasi harga
dan konfigurasi dicatat lengkap dengan nilai sebelum dan sesudah.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def record(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        before_value=_jsonable(before) if before is not None else None,
        after_value=_jsonable(after) if after is not None else None,
    )
    db.add(entry)
    return entry
