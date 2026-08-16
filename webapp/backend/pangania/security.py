"""Autentikasi admin — hashing kata sandi dan sesi cookie bertanda tangan.

Sengaja hanya memakai pustaka standar Python supaya tidak menambah dependensi
di lingkungan penelitian:

* Kata sandi  -> `hashlib.scrypt` (memory-hard, direkomendasikan untuk password).
* Sesi        -> payload JSON + tanda tangan HMAC-SHA256, disimpan pada cookie
                 httpOnly (PRD fitur #7).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from .config import SECRET_KEY, SESSION_MAX_AGE

# Parameter scrypt — seimbang antara keamanan dan waktu login yang wajar.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_LEN = 32


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


# ---------------------------------------------------------------------------
# Kata sandi
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _b64d(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64d(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, actual)


# ---------------------------------------------------------------------------
# Sesi
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionData:
    user_id: int
    email: str
    issued_at: int

    @property
    def expires_at(self) -> int:
        return self.issued_at + SESSION_MAX_AGE


def _sign(payload: bytes) -> str:
    return _b64e(hmac.new(SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).digest())


def create_session_token(user_id: int, email: str) -> str:
    payload = json.dumps(
        {"uid": user_id, "email": email, "iat": int(time.time())},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"{_b64e(payload)}.{_sign(payload)}"


def read_session_token(token: str | None) -> SessionData | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    try:
        payload = _b64d(encoded)
    except (ValueError, TypeError):
        return None

    if not hmac.compare_digest(_sign(payload), signature):
        return None

    try:
        data = json.loads(payload)
        issued_at = int(data["iat"])
        user_id = int(data["uid"])
        email = str(data["email"])
    except (ValueError, KeyError, TypeError):
        return None

    if time.time() > issued_at + SESSION_MAX_AGE:
        return None

    return SessionData(user_id=user_id, email=email, issued_at=issued_at)


# ---------------------------------------------------------------------------
# Rate limit login (in-memory; cukup untuk admin tunggal)
# ---------------------------------------------------------------------------


class LoginThrottle:
    def __init__(self, max_attempts: int, lockout_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._attempts: dict[str, list[float]] = {}

    def _prune(self, key: str) -> list[float]:
        now = time.time()
        recent = [t for t in self._attempts.get(key, []) if now - t < self.lockout_seconds]
        self._attempts[key] = recent
        return recent

    def is_locked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.max_attempts

    def seconds_remaining(self, key: str) -> int:
        recent = self._prune(key)
        if len(recent) < self.max_attempts:
            return 0
        return max(0, int(self.lockout_seconds - (time.time() - min(recent))))

    def register_failure(self, key: str) -> None:
        self._prune(key).append(time.time())

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)
