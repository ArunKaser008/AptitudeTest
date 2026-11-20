from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.models import User
from app.placement_schemas import TokenOut, UserOut

_PASSWORD_ROUNDS = 310_000
_TOKEN_TTL = timedelta(hours=8)
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PASSWORD_ROUNDS)
    return f"pbkdf2_sha256${_PASSWORD_ROUNDS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_rounds, raw_salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _decode(raw_salt), int(raw_rounds)
        )
        return hmac.compare_digest(_encode(actual), expected)
    except (ValueError, TypeError):
        return False


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(user: User) -> TokenOut:
    now = datetime.now(timezone.utc)
    expires_at = now + _TOKEN_TTL
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({
        "sub": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}"
    signature = hmac.new(
        get_settings().placement_auth_secret.encode(),
        unsigned.encode(),
        hashlib.sha256,
    ).digest()
    token = f"{unsigned}.{_encode(signature)}"
    return TokenOut(
        access_token=token,
        expires_at=expires_at,
        user=UserOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            college_id=user.college_id,
            batch_id=user.batch_id,
        ),
    )


def _token_user_id(token: str) -> UUID:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(
            get_settings().placement_auth_secret.encode(),
            unsigned.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_decode(signature), expected):
            raise ValueError("Invalid token signature.")
        claims = json.loads(_decode(payload))
        if int(claims["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("Expired token.")
        return UUID(claims["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token.") from error


def get_placement_user(
    db: DatabaseSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(status_code=401, detail="A bearer token is required.")
    user = db.scalar(select(User).where(User.id == _token_user_id(credentials.credentials)))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="The user is inactive or no longer exists.")
    return user


def require_roles(*roles: str):
    allowed = frozenset(roles)

    def dependency(user: User = Depends(get_placement_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="This role cannot access the requested resource.")
        return user

    return dependency
