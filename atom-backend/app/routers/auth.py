import jwt
from fastapi import APIRouter, HTTPException, status

from app.db import auth_lookup
from app.schemas import AccessOut, LoginIn, RefreshIn, TokenOut
from app.security import decode_token, make_access, make_refresh, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn) -> TokenOut:
    user = auth_lookup(body.email)
    if not user or not verify_password(user["senha_hash"], body.senha):
        # Same error for unknown email and wrong password (no user enumeration).
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    sub = str(user["user_id"])
    tid = str(user["tenant_id"])
    return TokenOut(
        access_token=make_access(sub, tid, user["role"]),
        refresh_token=make_refresh(sub, tid, user["role"]),
    )


@router.post("/refresh", response_model=AccessOut)
def refresh(body: RefreshIn) -> AccessOut:
    try:
        claims = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not a refresh token")
    return AccessOut(
        access_token=make_access(claims["sub"], claims["tenant_id"], claims.get("role", "user")),
    )
