from __future__ import annotations

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


class LoginPayload(BaseModel):
    username: str
    password: str


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
def login(payload: LoginPayload, response: Response):
    validate_auth_configuration()
    if not verify_login(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

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
