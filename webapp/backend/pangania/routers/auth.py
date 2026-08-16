"""Autentikasi admin (PRD fitur #7)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import (
    LOGIN_LOCKOUT_SECONDS,
    LOGIN_MAX_ATTEMPTS,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
)
from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import LoginRequest
from ..security import LoginThrottle, create_session_token, verify_password
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])

_throttle = LoginThrottle(LOGIN_MAX_ATTEMPTS, LOGIN_LOCKOUT_SECONDS)


def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "last_login_at": user.last_login_at,
    }


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    throttle_key = f"{client_ip}:{payload.email.lower()}"

    if _throttle.is_locked(throttle_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Terlalu banyak percobaan gagal. Coba lagi dalam "
                f"{_throttle.seconds_remaining(throttle_key)} detik."
            ),
        )

    user = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalars().first()

    # Pesan kesalahan sengaja sama untuk email tidak dikenal maupun kata sandi
    # salah, supaya tidak membocorkan email mana yang terdaftar.
    if user is None or not verify_password(payload.password, user.password_hash):
        _throttle.register_failure(throttle_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah.",
        )

    _throttle.reset(throttle_key)
    user.last_login_at = datetime.now()
    audit.record(db, user_id=user.id, action="login", entity="user", entity_id=user.id)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(user.id, user.email),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        # Di produksi (HTTPS) nilai ini harus True.
        secure=False,
        path="/",
    )
    return {"user": _serialize(user)}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": _serialize(user)}
