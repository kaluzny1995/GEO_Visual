"""Tests for :class:`SupabasePostgresProvider` (engine setup, queries and cleanup)."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import error
from model.config.supabase_config import SupabaseConnectionConfig
from provider.supabase_postgres.supabase_postgres_provider import SupabasePostgresProvider

CONNECTION_URL = "postgresql+psycopg://user:pass@db.example.com:6543/postgres?sslmode=require"
PROVIDER_MODULE = "provider.supabase_postgres.supabase_postgres_provider"


def make_provider(**kwargs: object) -> tuple[SupabasePostgresProvider, MagicMock, MagicMock, MagicMock]:
    """Build a provider around a mocked engine and return both connection mocks."""
    engine = MagicMock()
    connect_connection = engine.connect.return_value.__enter__.return_value
    begin_connection = engine.begin.return_value.__enter__.return_value
    provider = SupabasePostgresProvider(connection_url=CONNECTION_URL, db_engine=engine, **kwargs)
    return provider, engine, connect_connection, begin_connection


class TestSupabasePostgresProvider:
    """Tests for :class:`SupabasePostgresProvider`."""

    def test_connection_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without an explicit URL the provider reads ``.env`` credentials."""
        cfg = SupabaseConnectionConfig(
            username="user",
            password="pass",
            host="db.example.com",
            port=6543,
            database="postgres",
        )
        monkeypatch.setattr(SupabaseConnectionConfig, "from_env", staticmethod(lambda: cfg))
        with patch(f"{PROVIDER_MODULE}.create_engine"):
            provider = SupabasePostgresProvider()
        assert provider.connection_url == cfg.get_connection_url()

    def test_engine_is_created_with_pooler_safe_options(self) -> None:
        """The engine uses pre-ping, pooling and psycopg's prepared-statement workaround."""
        with patch(f"{PROVIDER_MODULE}.create_engine") as create_engine:
            SupabasePostgresProvider(
                connection_url=CONNECTION_URL,
                connect_timeout=7,
                pool_size=3,
                max_overflow=2,
                pool_recycle=120,
            )
        create_engine.assert_called_once_with(
            CONNECTION_URL,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_recycle=120,
            connect_args={"prepare_threshold": None, "connect_timeout": 7},
        )

    def test_connect_runs_select_one(self) -> None:
        """``connect`` checks out a connection and runs ``SELECT 1``."""
        provider, _, connection, _ = make_provider()
        provider.connect()
        connection.execute.assert_called_once()
        assert "SELECT 1" in str(connection.execute.call_args.args[0])

    def test_read_dataframe_returns_pandas_frame(self) -> None:
        """``read_dataframe`` binds parameters, caps rows and sets the timeout."""
        provider, _, _, connection = make_provider()
        expected = pd.DataFrame({"source_name": ["usgs"]})
        with patch(f"{PROVIDER_MODULE}.pd.read_sql_query", return_value=expected) as read_sql:
            result = provider.read_dataframe(
                "SELECT * FROM geo.union_etl WHERE source_name = :source;",
                {"source": "usgs"},
                max_rows=10,
                statement_timeout_ms=5_000,
            )
        assert result is expected
        query = str(read_sql.call_args.args[0])
        assert "SELECT * FROM geo.union_etl WHERE source_name = :source" in query
        assert "LIMIT 11" in query
        assert read_sql.call_args.args[1] is connection
        assert read_sql.call_args.kwargs["params"] == {"source": "usgs"}
        assert "SET LOCAL statement_timeout = 5000" in str(connection.execute.call_args.args[0])

    def test_read_dataframe_uses_provider_defaults(self) -> None:
        """Per-query limits fall back to the provider's configured defaults."""
        provider, _, _, connection = make_provider(max_rows=25, statement_timeout_ms=1_000)
        with patch(f"{PROVIDER_MODULE}.pd.read_sql_query", return_value=pd.DataFrame()) as read_sql:
            provider.read_dataframe("SELECT 1")
        assert "LIMIT 26" in str(read_sql.call_args.args[0])
        assert "SET LOCAL statement_timeout = 1000" in str(connection.execute.call_args.args[0])

    def test_read_dataframe_rejects_oversized_result(self) -> None:
        """A result larger than the cap raises instead of growing the app's memory."""
        provider, _, _, _ = make_provider()
        oversized = pd.DataFrame({"id": [1, 2, 3]})
        with (
            patch(f"{PROVIDER_MODULE}.pd.read_sql_query", return_value=oversized),
            pytest.raises(error.QueryTooLargeError, match="more than 2 rows"),
        ):
            provider.read_dataframe("SELECT id FROM geo.union_etl", max_rows=2)

    def test_read_dataframe_rejects_an_empty_query(self) -> None:
        """An empty query fails before touching the database."""
        provider, _, _, _ = make_provider()
        with pytest.raises(ValueError, match="query must not be empty"):
            provider.read_dataframe("  ;  ")

    def test_read_dataframe_rejects_non_positive_limits(self) -> None:
        """Row caps and timeouts must be positive."""
        provider, _, _, _ = make_provider()
        with pytest.raises(ValueError, match="max_rows must be positive"):
            provider.read_dataframe("SELECT 1", max_rows=0)
        with pytest.raises(ValueError, match="statement_timeout_ms must be positive"):
            provider.read_dataframe("SELECT 1", statement_timeout_ms=0)

    def test_read_scalar_returns_the_first_value(self) -> None:
        """``read_scalar`` returns the first column of the first row."""
        provider, _, _, _ = make_provider()
        frame = pd.DataFrame({"count": [42]})
        with patch(f"{PROVIDER_MODULE}.pd.read_sql_query", return_value=frame):
            assert provider.read_scalar("SELECT COUNT(*) AS count FROM geo.union_etl") == 42

    def test_read_scalar_returns_none_for_an_empty_result(self) -> None:
        """``read_scalar`` returns ``None`` when the query has no rows."""
        provider, _, _, _ = make_provider()
        with patch(f"{PROVIDER_MODULE}.pd.read_sql_query", return_value=pd.DataFrame()):
            assert provider.read_scalar("SELECT COUNT(*) AS count FROM geo.union_etl") is None

    def test_list_tables_inspects_the_requested_schema(self) -> None:
        """``list_tables`` passes the schema to SQLAlchemy's inspector."""
        provider, engine, _, _ = make_provider()
        with patch(f"{PROVIDER_MODULE}.sqlalchemy.inspect") as inspect:
            inspect.return_value.get_table_names.return_value = ["union_etl", "data_quality"]
            tables = provider.list_tables("geo")
        assert tables == ["union_etl", "data_quality"]
        inspect.assert_called_once_with(engine)
        inspect.return_value.get_table_names.assert_called_once_with(schema="geo")

    def test_close_disposes_the_engine(self) -> None:
        """``close`` releases the engine's connection pool."""
        provider, engine, _, _ = make_provider()
        provider.close()
        engine.dispose.assert_called_once()
