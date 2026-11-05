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


CHECK_CONNECTION_CASES = [
    pytest.param(_MissingConfig, None, False, "not configured", False, id="missing-credentials"),
    pytest.param(_ValidConfig, None, True, "Connected to Supabase", True, id="connected"),
    pytest.param(_ValidConfig, SQLAlchemyError("boom"), False, "Could not connect", True, id="connection-error"),
]


class TestCheckConnection:
    """Tests for :func:`check_connection`."""

    @pytest.mark.parametrize(
        "config_stub, connect_error, expected_connected, expected_message, provider_called",
        CHECK_CONNECTION_CASES,
    )
    def test_check_connection(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_stub: type,
        connect_error: Exception | None,
        expected_connected: bool,
        expected_message: str,
        provider_called: bool,
    ) -> None:
        """Each connection scenario becomes a short, non-fatal status."""
        provider = MagicMock()
        if connect_error is not None:
            provider.connect.side_effect = connect_error
        monkeypatch.setattr(database, "SupabaseConnectionConfig", config_stub)
        monkeypatch.setattr(database, "get_provider", lambda: provider)

        status = database.check_connection()

        assert status.connected is expected_connected
        assert expected_message in status.message
        assert provider.connect.call_count == (1 if provider_called else 0)


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
