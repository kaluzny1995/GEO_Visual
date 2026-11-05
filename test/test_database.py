"""Tests for the Streamlit-facing database helpers."""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from sqlalchemy.exc import SQLAlchemyError

from model.config.supabase_config import SupabaseConnectionConfig
from utils import database


class _MissingConfig:
    """Stand-in for :class:`SupabaseConnectionConfig` without credentials."""

    @staticmethod
    def from_env() -> SupabaseConnectionConfig:
        raise ValueError("Missing Supabase credentials: SUPABASE_DB_USER")


class _ValidConfig:
    """Stand-in for :class:`SupabaseConnectionConfig` with credentials."""

    @staticmethod
    def from_env() -> SupabaseConnectionConfig:
        return SupabaseConnectionConfig(
            username="user",
            password="pass",
            host="db.example.com",
            port=6543,
            database="postgres",
        )


class TestCheckConnection:
    """Tests for :func:`check_connection`."""

    def test_missing_credentials_are_reported_without_raising(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing ``.env`` produces a friendly, non-fatal status."""
        monkeypatch.setattr(database, "SupabaseConnectionConfig", _MissingConfig)
        status = database.check_connection()
        assert status.connected is False
        assert "not configured" in status.message.lower()

    def test_successful_connection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A reachable database produces a connected status."""
        provider = MagicMock()
        monkeypatch.setattr(database, "SupabaseConnectionConfig", _ValidConfig)
        monkeypatch.setattr(database, "get_provider", lambda: provider)
        status = database.check_connection()
        assert status.connected is True
        assert status.message == "Connected to Supabase"
        provider.connect.assert_called_once()

    def test_connection_failure_is_reported_without_raising(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A database error is logged and shown as a short status message."""
        provider = MagicMock()
        provider.connect.side_effect = SQLAlchemyError("boom")
        monkeypatch.setattr(database, "SupabaseConnectionConfig", _ValidConfig)
        monkeypatch.setattr(database, "get_provider", lambda: provider)
        status = database.check_connection()
        assert status.connected is False
        assert "Could not connect" in status.message


class TestCachedQuery:
    """Tests for :func:`cached_query`."""

    def test_forwards_hashable_params_and_row_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The Streamlit cache wrapper forwards parameters and the per-query cap."""
        provider = MagicMock()
        expected = pd.DataFrame({"count": [7]})
        provider.read_dataframe.return_value = expected
        monkeypatch.setattr(database, "get_provider", lambda: provider)
        result = database.cached_query(
            "SELECT COUNT(*) AS count FROM geo.union_etl WHERE source_name = :source",
            (("source", "usgs"),),
            max_rows=10,
        )
        pd.testing.assert_frame_equal(result, expected)
        provider.read_dataframe.assert_called_once_with(
            "SELECT COUNT(*) AS count FROM geo.union_etl WHERE source_name = :source",
            {"source": "usgs"},
            max_rows=10,
        )
