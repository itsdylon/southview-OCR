from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from southview.auth import (
    SESSION_COOKIE_NAME,
    get_auth_settings,
    get_authenticated_user,
    issue_session_token,
    validate_auth_configuration,
    verify_login,
)

router = APIRouter(tags=["auth"])
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_LOCKOUT_SECONDS = 15 * 60
_MAX_LOGIN_ATTEMPTS = 5
_FAILED_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_LOCKOUTS: dict[str, float] = {}


class LoginPayload(BaseModel):
    username: str
    password: str


def _client_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _recent_attempts(client_key: str, now: float) -> list[float]:
    attempts = [
        attempt
        for attempt in _FAILED_LOGIN_ATTEMPTS.get(client_key, [])
        if now - attempt <= _LOGIN_WINDOW_SECONDS
    ]
    _FAILED_LOGIN_ATTEMPTS[client_key] = attempts
    return attempts


def _enforce_login_rate_limit(client_key: str, now: float) -> None:
    locked_until = _LOGIN_LOCKOUTS.get(client_key)
    if locked_until is None:
        return
    if locked_until <= now:
        _LOGIN_LOCKOUTS.pop(client_key, None)
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Try again later.",
    )


def _record_failed_login(client_key: str, now: float) -> None:
    attempts = _recent_attempts(client_key, now)
    attempts.append(now)
    _FAILED_LOGIN_ATTEMPTS[client_key] = attempts
    if len(attempts) >= _MAX_LOGIN_ATTEMPTS:
        _LOGIN_LOCKOUTS[client_key] = now + _LOGIN_LOCKOUT_SECONDS


def _clear_failed_logins(client_key: str) -> None:
    _FAILED_LOGIN_ATTEMPTS.pop(client_key, None)
    _LOGIN_LOCKOUTS.pop(client_key, None)


@router.get("/auth/session")
def get_session(request: Request):
    settings = get_auth_settings()
    try:
        username = get_authenticated_user(request)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return {"authenticated": False, "username": settings.username}
        raise
    return {"authenticated": True, "username": username}


@router.post("/auth/login")
def login(payload: LoginPayload, request: Request, response: Response):
    validate_auth_configuration()
    client_key = _client_key(request)
    now = time.time()
    _enforce_login_rate_limit(client_key, now)
    if not verify_login(payload.username, payload.password):
        _record_failed_login(client_key, now)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    _clear_failed_logins(client_key)
    settings = get_auth_settings()
    token = issue_session_token(payload.username)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
        path="/",
    )
    return {"authenticated": True, "username": payload.username}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return {"authenticated": False}
