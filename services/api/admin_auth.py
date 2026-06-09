from __future__ import annotations

import base64
import hmac
import os
import time
from hashlib import sha256

from fastapi import HTTPException, Request, Response, status


ADMIN_USERNAME = "root"
ADMIN_PASSWORD = "Dramepulse"
ADMIN_SESSION_COOKIE = "dramepulse_admin_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


def _secret() -> bytes:
    return os.getenv("DRAMEPULSE_ADMIN_SESSION_SECRET", "dramepulse-admin-dev-secret").encode("utf-8")


def _sign(message: str) -> str:
    return hmac.new(_secret(), message.encode("utf-8"), sha256).hexdigest()


def create_admin_session_token(username: str = ADMIN_USERNAME) -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    message = f"{username}:{expires_at}"
    signature = _sign(message)
    raw = f"{message}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def validate_admin_session_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, expires_at_raw, signature = decoded.rsplit(":", 2)
        expires_at = int(expires_at_raw)
    except Exception:
        return False
    if username != ADMIN_USERNAME or expires_at < int(time.time()):
        return False
    return hmac.compare_digest(signature, _sign(f"{username}:{expires_at}"))


def set_admin_session_cookie(response: Response) -> None:
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        create_admin_session_token(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_admin_session_cookie(response: Response) -> None:
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/")


def require_admin(request: Request) -> None:
    if not validate_admin_session_token(request.cookies.get(ADMIN_SESSION_COOKIE)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")


def authenticate_admin(username: str, password: str) -> bool:
    return hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD)
