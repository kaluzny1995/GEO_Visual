"""Tests for :class:`SupabaseConnectionConfig` (env loading and connection URL)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from model.config import supabase_config
from model.config.supabase_config import SupabaseConnectionConfig

VALID_CONFIG = {
    "username": "user",
    "password": "pass",
    "host": "db.example.com",
    "port": 5432,
    "database": "postgres",
}

VALID_ENV = {
    "SUPABASE_DB_USER": "user",
    "SUPABASE_DB_PASSWORD": "pass",
    "SUPABASE_DB_HOST": "db.example.com",
    "SUPABASE_DB_PORT": "5432",
    "SUPABASE_DB_NAME": "postgres",
}


@pytest.fixture
def env_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all five ``SUPABASE_DB_*`` environment variables to valid values."""
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)


class TestSupabaseConnectionConfig:
    """Tests for :class:`SupabaseConnectionConfig`."""

    def test_valid(self) -> None:
        """A full set of valid credentials constructs a config."""
        cfg = SupabaseConnectionConfig(**VALID_CONFIG)
        assert cfg.username == "user"
        assert cfg.password == "pass"
        assert cfg.host == "db.example.com"
        assert cfg.port == 5432
        assert cfg.database == "postgres"

    def test_frozen(self) -> None:
        """The config model is immutable (frozen)."""
        cfg = SupabaseConnectionConfig(**VALID_CONFIG)
        with pytest.raises(ValidationError):
            cfg.host = "other.example.com"

    def test_from_env(self, env_config: None) -> None:
        """``from_env`` builds the config from environment variables."""
        cfg = SupabaseConnectionConfig.from_env()
        assert cfg.username == "user"
        assert cfg.password == "pass"
        assert cfg.host == "db.example.com"
        assert cfg.port == 5432
        assert cfg.database == "postgres"

    def test_from_env_missing_all_vars(self) -> None:
        """``from_env`` lists every missing variable in the error message."""
        with pytest.raises(ValueError, match="Missing Supabase credentials") as exc_info:
            SupabaseConnectionConfig.from_env()
        for name in VALID_ENV:
            assert name in str(exc_info.value)

    def test_from_env_missing_single_var(self, env_config: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """``from_env`` fails when one required variable is deleted."""
        monkeypatch.delenv("SUPABASE_DB_PASSWORD")
        with pytest.raises(ValueError, match=r"Missing Supabase credentials: SUPABASE_DB_PASSWORD\b"):
            SupabaseConnectionConfig.from_env()

    def test_from_env_empty_value_counts_as_missing(self, env_config: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty variable value counts as missing."""
        monkeypatch.setenv("SUPABASE_DB_PASSWORD", "")
        with pytest.raises(ValueError, match=r"Missing Supabase credentials: SUPABASE_DB_PASSWORD\b"):
            SupabaseConnectionConfig.from_env()

    def test_from_env_invalid_port(self, env_config: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-integer ``SUPABASE_DB_PORT`` raises a descriptive error."""
        monkeypatch.setenv("SUPABASE_DB_PORT", "not-a-number")
        with pytest.raises(ValueError, match="SUPABASE_DB_PORT must be an integer"):
            SupabaseConnectionConfig.from_env()

    def test_from_env_loads_dotenv_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Credentials are loaded from a ``.env`` file when no variables are set."""
        dotenv_file = tmp_path / ".env"
        dotenv_file.write_text("\n".join(f"{name}={value}" for name, value in VALID_ENV.items()) + "\n")
        monkeypatch.setattr(supabase_config, "DOTENV_PATH", str(dotenv_file))
        cfg = SupabaseConnectionConfig.from_env()
        assert cfg.host == "db.example.com"
        assert cfg.port == 5432

    def test_from_env_environment_overrides_dotenv(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Environment variables take precedence over ``.env`` values."""
        dotenv_file = tmp_path / ".env"
        dotenv_file.write_text("SUPABASE_DB_HOST=from-file.example.com\n")
        monkeypatch.setattr(supabase_config, "DOTENV_PATH", str(dotenv_file))
        for name, value in VALID_ENV.items():
            monkeypatch.setenv(name, value)
        cfg = SupabaseConnectionConfig.from_env()
        assert cfg.host == "db.example.com"

    def test_get_connection_url(self) -> None:
        """``get_connection_url`` builds the psycopg URL with TLS."""
        cfg = SupabaseConnectionConfig(**VALID_CONFIG)
        assert cfg.get_connection_url() == (
            "postgresql+psycopg://user:pass@db.example.com:5432/postgres?sslmode=require"
        )

    def test_get_connection_url_encodes_special_characters(self) -> None:
        """Credentials with special characters are URL-encoded."""
        cfg = SupabaseConnectionConfig(
            username="postgres.ref",
            password="p@ss/w:rd",
            host="db.example.com",
            port=6543,
            database="postgres",
        )
        assert cfg.get_connection_url() == (
            "postgresql+psycopg://postgres.ref:p%40ss%2Fw%3Ard@db.example.com:6543/postgres?sslmode=require"
        )
