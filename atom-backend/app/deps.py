"""Request auth: decode the bearer JWT into the current user + tenant.

``tenant_id`` is derived ONLY from the JWT, never from the request body/query.
"""
from collections.abc import Iterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.engine import Connection

from app.db import tenant_tx
from app.security import decode_token


@dataclass
class CurrentUser:
    user_id: str
    tenant_id: str
    role: str


def current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    if claims.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not an access token")
    return CurrentUser(
        user_id=claims["sub"],
        tenant_id=claims["tenant_id"],
        role=claims.get("role", "user"),
    )


def tenant_conn(user: CurrentUser = Depends(current_user)) -> Iterator[Connection]:
    """A tenant-scoped DB transaction (RLS active) for the authenticated tenant."""
    with tenant_tx(user.tenant_id) as conn:
        yield conn
