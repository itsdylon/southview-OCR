"""Configuration loading from config.yaml."""

from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    with open(path) as f:
        return yaml.safe_load(f)


_config: dict[str, Any] | None = None


def get_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Get cached configuration, loading if necessary."""
    global _config
    if _config is None:
        _config = load_config(config_path)
    return _config
