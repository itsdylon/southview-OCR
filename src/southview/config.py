"""Configuration loading from config.yaml."""

import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"
_DEFAULT_DOTENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    with open(path) as f:
        return yaml.safe_load(f)


_config: dict[str, Any] | None = None
_dotenv_loaded = False


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export "):].strip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if value and value[0] in {'"', "'"} and value[-1:] == value[0]:
        value = value[1:-1]
    elif " #" in value:
        value = value.split(" #", 1)[0].rstrip()

    return key, value


def load_dotenv(dotenv_path: Path | str | None = None, *, override: bool = False) -> None:
    """
    Load key/value pairs from a .env file into os.environ.

    Existing environment variables are preserved unless override=True.
    """
    path = Path(dotenv_path) if dotenv_path else _DEFAULT_DOTENV_PATH
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if not parsed:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value


def get_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Get cached configuration, loading if necessary."""
    global _config, _dotenv_loaded
    if not _dotenv_loaded:
        # For local dev, prefer .env so stale exported vars do not linger.
        load_dotenv(override=True)
        _dotenv_loaded = True
    if _config is None:
        _config = load_config(config_path)
    return _config
