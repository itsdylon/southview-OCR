import os

from southview import config as app_config


def test_load_dotenv_sets_missing_values(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "# comment",
                "GEMINI_API_KEY=abc123",
                'export GOOGLE_API_KEY="quoted-value"',
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    app_config.load_dotenv(dotenv_path)

    assert os.getenv("GEMINI_API_KEY") == "abc123"
    assert os.getenv("GOOGLE_API_KEY") == "quoted-value"


def test_load_dotenv_does_not_override_existing_env(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("GEMINI_API_KEY=from-file", encoding="utf-8")

    monkeypatch.setenv("GEMINI_API_KEY", "already-set")
    app_config.load_dotenv(dotenv_path)

    assert os.getenv("GEMINI_API_KEY") == "already-set"


def test_load_dotenv_can_override_existing_env(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("GEMINI_API_KEY=from-file", encoding="utf-8")

    monkeypatch.setenv("GEMINI_API_KEY", "already-set")
    app_config.load_dotenv(dotenv_path, override=True)

    assert os.getenv("GEMINI_API_KEY") == "from-file"


def test_get_config_loads_default_dotenv_once(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("api:\n  host: 127.0.0.1\n  port: 8000\n", encoding="utf-8")

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("GEMINI_API_KEY=from-dotenv", encoding="utf-8")

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(app_config, "_DEFAULT_DOTENV_PATH", dotenv_path)
    monkeypatch.setattr(app_config, "_dotenv_loaded", False)
    monkeypatch.setattr(app_config, "_config", None)

    cfg = app_config.get_config(cfg_path)

    assert cfg["api"]["host"] == "127.0.0.1"
    assert os.getenv("GEMINI_API_KEY") == "from-dotenv"


def test_get_config_overrides_stale_exported_value(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("api:\n  host: 127.0.0.1\n  port: 8000\n", encoding="utf-8")

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("GEMINI_API_KEY=from-dotenv", encoding="utf-8")

    monkeypatch.setenv("GEMINI_API_KEY", "stale-exported-value")
    monkeypatch.setattr(app_config, "_DEFAULT_DOTENV_PATH", dotenv_path)
    monkeypatch.setattr(app_config, "_dotenv_loaded", False)
    monkeypatch.setattr(app_config, "_config", None)

    app_config.get_config(cfg_path)

    assert os.getenv("GEMINI_API_KEY") == "from-dotenv"
