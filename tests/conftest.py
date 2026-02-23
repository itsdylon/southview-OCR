"""Shared test fixtures."""

import tempfile
from pathlib import Path

import pytest

from southview.db.engine import init_db


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    engine = init_db(db_path)
    yield db_path
