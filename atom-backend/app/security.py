"""Password hashing (argon2id) and JWT issue/verify."""
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def _token(sub: str, tenant_id: str, role: str, kind: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
        "type": kind,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def make_access(sub: str, tenant_id: str, role: str) -> str:
    return _token(sub, tenant_id, role, "access", timedelta(minutes=settings.access_ttl_min))


def make_refresh(sub: str, tenant_id: str, role: str) -> str:
    return _token(sub, tenant_id, role, "refresh", timedelta(days=settings.refresh_ttl_days))


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError (incl. ExpiredSignatureError) on invalid/expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
