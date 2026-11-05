"""Shared test fixtures."""

import pytest

from model.config import supabase_config
from utils import database


@pytest.fixture(autouse=True)
def isolated_supabase_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the real ``.env`` and ambient Supabase variables out of every test."""
    monkeypatch.setattr(supabase_config, "DOTENV_PATH", "/nonexistent/.env")
    for name in supabase_config.REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    database.get_provider.clear()
    database.cached_connection_status.clear()
    database.cached_query.clear()
