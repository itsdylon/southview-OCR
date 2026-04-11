from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fastapi import HTTPException, Request, status

PBKDF2_PREFIX: Final[str] = "pbkdf2_sha256"
SESSION_COOKIE_NAME: Final[str] = "southview_session"
_DUMMY_PASSWORD_HASH: Final[str] = (
    "pbkdf2_sha256$310000$southview-dummy-salt$"
    "Zy6k2AoYPwzlGjCpdfs+ZgLxmGpnW6iopukYY0J5ikI="
)
_ENV_LOADED = False
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class AuthSettings:
    username: str
    password_hash: str | None
    session_secret: str | None
    secure_cookies: bool
    session_ttl_seconds: int


def get_auth_settings() -> AuthSettings:
    _load_env_file()
    app_env = _normalized_env(os.getenv("SOUTHVIEW_ENV"))
    return AuthSettings(
        username=os.getenv("SOUTHVIEW_AUTH_USERNAME", "admin"),
        password_hash=os.getenv("SOUTHVIEW_AUTH_PASSWORD_HASH"),
        session_secret=os.getenv("SOUTHVIEW_AUTH_SESSION_SECRET"),
        secure_cookies=_secure_cookies_enabled(app_env, os.getenv("SOUTHVIEW_AUTH_SECURE_COOKIES")),
        session_ttl_seconds=int(os.getenv("SOUTHVIEW_AUTH_SESSION_TTL_SECONDS", "43200")),
    )


def validate_auth_configuration() -> None:
    settings = get_auth_settings()
    if not settings.password_hash or not settings.session_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication is not configured. Set SOUTHVIEW_AUTH_PASSWORD_HASH "
                "and SOUTHVIEW_AUTH_SESSION_SECRET."
            ),
        )


def verify_login(username: str, password: str) -> bool:
    settings = get_auth_settings()
    username_matches = hmac.compare_digest(username, settings.username)
    password_hash = settings.password_hash or _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)
    return bool(settings.password_hash) and username_matches and password_matches


def issue_session_token(username: str) -> str:
    settings = get_auth_settings()
    if not settings.session_secret:
        raise RuntimeError("Missing SOUTHVIEW_AUTH_SESSION_SECRET")
    payload = {
        "sub": username,
        "exp": int(time.time()) + settings.session_ttl_seconds,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = _encode_payload(payload)
    signature = _sign_value(encoded, settings.session_secret)
    return f"{encoded}.{signature}"


def get_authenticated_user(request: Request) -> str:
    settings = get_auth_settings()
    if not settings.session_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    username = verify_session_token(token, settings.session_secret)
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return username


def verify_session_token(token: str, secret: str) -> str | None:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = _sign_value(encoded, secret)
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(base64.urlsafe_b64decode(_pad_base64(encoded)))
    except (ValueError, json.JSONDecodeError):
        return None

    if payload.get("exp", 0) < int(time.time()):
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    return subject


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected_hash = encoded_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != PBKDF2_PREFIX:
        return False

    computed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    )
    actual_hash = base64.b64encode(computed).decode("ascii")
    return hmac.compare_digest(actual_hash, expected_hash)


def hash_password(password: str, iterations: int = 310_000) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    encoded = base64.b64encode(derived).decode("ascii")
    return f"{PBKDF2_PREFIX}${iterations}${salt}${encoded}"


def _sign_value(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _encode_payload(payload: dict[str, object]) -> str:
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")


def _pad_base64(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalized_env(value: str | None) -> str:
    return (value or "production").strip().lower()


def _secure_cookies_enabled(app_env: str, configured_value: str | None) -> bool:
    """Keep secure cookies on by default outside explicit local development."""
    if app_env == "development":
        return _parse_bool(configured_value, default=False)
    return True


def _load_env_file() -> None:
    global _ENV_LOADED
    if _ENV_LOADED or not _ENV_PATH.exists():
        _ENV_LOADED = True
        return

    for raw_line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

    _ENV_LOADED = True
