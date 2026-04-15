"""Integration tests for settings endpoints."""

import os
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient
import pytest

from southview.api.app import create_app
from southview.auth import hash_password


@pytest.fixture
def client(tmp_config):
    auth_env = {
        "SOUTHVIEW_ENV": "development",
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
            login_response = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "test-password"},
            )
            assert login_response.status_code == 200
            yield client


def test_update_thresholds_persists_yaml_values(client, tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "ocr": {
                    "confidence": {
                        "auto_approve": 0.85,
                        "review_threshold": 0.70,
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime_config = {
        "ocr": {
            "confidence": {
                "auto_approve": 0.85,
                "review_threshold": 0.70,
            }
        }
    }
    monkeypatch.setattr("southview.api.routes.settings.get_config", lambda: runtime_config)
    monkeypatch.setattr("southview.api.routes.settings._DEFAULT_CONFIG_PATH", config_path)

    response = client.put(
        "/api/settings/thresholds",
        json={"auto_approve": 0.9, "review_threshold": 0.75},
    )

    assert response.status_code == 200
    assert runtime_config["ocr"]["confidence"]["auto_approve"] == 0.9
    assert runtime_config["ocr"]["confidence"]["review_threshold"] == 0.75

    persisted = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert persisted["ocr"]["confidence"]["auto_approve"] == 0.9
    assert persisted["ocr"]["confidence"]["review_threshold"] == 0.75


def test_update_thresholds_rejects_out_of_range_values(client):
    response = client.put(
        "/api/settings/thresholds",
        json={"auto_approve": 1.5, "review_threshold": -0.1},
    )

    assert response.status_code == 422


def test_update_thresholds_uses_file_locking(client, tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "ocr": {
                    "confidence": {
                        "auto_approve": 0.85,
                        "review_threshold": 0.70,
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime_config = {
        "ocr": {
            "confidence": {
                "auto_approve": 0.85,
                "review_threshold": 0.70,
            }
        }
    }
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr("southview.api.routes.settings.get_config", lambda: runtime_config)
    monkeypatch.setattr("southview.api.routes.settings._DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setattr(
        "southview.api.routes.settings.fcntl.flock",
        lambda fileno, operation: calls.append((fileno, operation)),
    )

    response = client.put(
        "/api/settings/thresholds",
        json={"auto_approve": 0.88, "review_threshold": 0.74},
    )

    assert response.status_code == 200
    assert len(calls) == 2
