"""Auth integration tests."""

from contextlib import contextmanager
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from southview.api.app import create_app
from southview.auth import hash_password


@contextmanager
def make_client(tmp_config):
    auth_env = {
        "SOUTHVIEW_AUTH_USERNAME": "admin",
        "SOUTHVIEW_AUTH_PASSWORD_HASH": hash_password("test-password"),
        "SOUTHVIEW_AUTH_SESSION_SECRET": "test-session-secret",
        "SOUTHVIEW_AUTH_SECURE_COOKIES": "false",
    }
    with patch.dict(os.environ, auth_env, clear=False), \
         patch("southview.api.app.init_db"), \
         patch("southview.api.app.get_config", return_value=tmp_config):
        app = create_app()
        with TestClient(app) as client:
            yield client


def test_protected_route_requires_login(tmp_config):
    with make_client(tmp_config) as client:
        response = client.get("/api/videos")
        assert response.status_code == 401


def test_login_sets_session_and_unlocks_api(tmp_config):
    with make_client(tmp_config) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "test-password"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["authenticated"] is True

        session_response = client.get("/api/auth/session")
        assert session_response.status_code == 200
        assert session_response.json() == {"authenticated": True, "username": "admin"}

        protected_response = client.get("/api/videos")
        assert protected_response.status_code == 200
        assert protected_response.json() == []


def test_invalid_login_is_rejected(tmp_config):
    with make_client(tmp_config) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]
