import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from .config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_token(data: dict, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = data.copy()
    payload.update({"iat": now, "exp": now + expires_delta, "type": token_type})
    if token_type == "refresh":
        payload["jti"] = secrets.token_hex(16)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict) -> str:
    return _create_token(
        data, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(data: dict) -> str:
    return _create_token(
        data, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def _decode_token(token: str, expected_type: str) -> dict:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
        subject = payload.get("sub")
        if not subject or payload.get("type") != expected_type:
            raise exc
        UUID(str(subject))
        return payload
    except jwt.PyJWTError, ValueError, TypeError:
        raise exc


def verify_access_token(token: str) -> dict:
    return _decode_token(token, "access")


def verify_refresh_token(token: str) -> dict:
    return _decode_token(token, "refresh")
