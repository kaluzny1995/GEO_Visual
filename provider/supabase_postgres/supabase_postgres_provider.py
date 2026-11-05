"""Supabase Postgres provider (SQLAlchemy 2.0 sync engine + psycopg 3)."""

import logging
from collections.abc import Mapping
from typing import Any

import pandas as pd
import sqlalchemy
from sqlalchemy import Engine, create_engine, text

import error
from model.config.supabase_config import SupabaseConnectionConfig

DEFAULT_MAX_ROWS = 50_000
DEFAULT_STATEMENT_TIMEOUT_MS = 30_000
DEFAULT_POOL_RECYCLE_SECONDS = 300


class SupabasePostgresProvider:
    """Read-only Supabase Postgres provider for the Streamlit data layer.

    Streamlit runs a synchronous script per interaction, so this provider uses
    a synchronous SQLAlchemy engine. The engine is pooled and normally created
    once per process and cached with ``st.cache_resource``.

    Every dataframe query is guarded: it runs with a PostgreSQL statement
    timeout and a row cap, so an accidental ``SELECT *`` cannot pull an entire
    table into the Streamlit process. Aggregate and filter in SQL; only the
    small result needed for a chart should cross the network.

    Attributes:
        connection_url: SQLAlchemy psycopg connection URL.
        db_engine: SQLAlchemy engine (connection pool).
        max_rows: Default row cap for a single dataframe query.
        statement_timeout_ms: Default per-query PostgreSQL statement timeout.
        logger: Provider logger.
    """

    connection_url: str
    db_engine: Engine
    max_rows: int
    statement_timeout_ms: int
    logger: logging.Logger

    def __init__(
        self,
        connection_url: str | None = None,
        db_engine: Engine | None = None,
        connect_timeout: int = 10,
        pool_size: int = 5,
        max_overflow: int = 5,
        pool_recycle: int = DEFAULT_POOL_RECYCLE_SECONDS,
        max_rows: int = DEFAULT_MAX_ROWS,
        statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the provider.

        Args:
            connection_url: Explicit connection URL. Defaults to the URL built
                from ``.env`` credentials via :class:`SupabaseConnectionConfig`.
            db_engine: Pre-built engine. Defaults to a new pooled engine on
                ``connection_url``.
            connect_timeout: Seconds before a connection attempt gives up.
            pool_size: Number of connections kept in the pool.
            max_overflow: Extra connections allowed above ``pool_size``.
            pool_recycle: Recycle pooled connections after this many seconds.
            max_rows: Default row cap for a single dataframe query.
            statement_timeout_ms: Default per-query PostgreSQL statement timeout.
            logger: Custom logger. Defaults to the module logger.
        """
        self.connection_url = connection_url or SupabaseConnectionConfig.from_env().get_connection_url()
        # psycopg 3 prepares statements after a few executions. The Supabase
        # transaction pooler reuses one server connection for many clients, so
        # cached named statements can collide — disable the cache, the psycopg 3
        # counterpart of asyncpg's `prepared_statement_cache_size=0`.
        self.db_engine = db_engine or create_engine(
            self.connection_url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            connect_args={"prepare_threshold": None, "connect_timeout": connect_timeout},
        )
        self.max_rows = self._positive_int(max_rows, "max_rows")
        self.statement_timeout_ms = self._positive_int(statement_timeout_ms, "statement_timeout_ms")
        self.logger = logger or logging.getLogger(__name__)

    def connect(self) -> None:
        """Verify that the database is reachable by running ``SELECT 1``.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If the connection cannot be established.
        """
        with self.db_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        self.logger.info("Connected to Supabase Postgres")

    def read_dataframe(
        self,
        query: str,
        params: Mapping[str, Any] | None = None,
        max_rows: int | None = None,
        statement_timeout_ms: int | None = None,
    ) -> pd.DataFrame:
        """Run a guarded read-only SQL query and return the result as a DataFrame.

        The query is wrapped in a subquery with a ``LIMIT`` one row above the
        cap, so an oversized result is detected without transferring the whole
        table. It also runs inside a transaction with ``SET LOCAL
        statement_timeout`` so a slow query cannot occupy the connection
        indefinitely.

        Args:
            query: Single SELECT statement with optional ``:named`` parameters.
                A trailing semicolon is allowed; multiple statements are not.
            params: Values bound to the query's named parameters.
            max_rows: Per-query row cap. Defaults to the provider's ``max_rows``.
            statement_timeout_ms: Per-query timeout. Defaults to the provider's
                ``statement_timeout_ms``.

        Returns:
            The query result as a pandas DataFrame.

        Raises:
            QueryTooLargeError: If the query returns more than ``max_rows`` rows.
            ValueError: If the query is empty or a limit/timeout is not positive.
            sqlalchemy.exc.SQLAlchemyError: If the query cannot be executed.
        """
        row_limit = self._positive_int(max_rows if max_rows is not None else self.max_rows, "max_rows")
        timeout_ms = self._positive_int(
            statement_timeout_ms if statement_timeout_ms is not None else self.statement_timeout_ms,
            "statement_timeout_ms",
        )
        guarded_query = self._with_row_limit(query, row_limit)

        with self.db_engine.begin() as connection:
            connection.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            frame = pd.read_sql_query(text(guarded_query), connection, params=params)

        if len(frame) > row_limit:
            raise error.QueryTooLargeError(
                f"Query returned more than {row_limit} rows. "
                "Aggregate or filter in SQL, or pass a larger max_rows explicitly."
            )
        return frame

    def read_scalar(self, query: str, params: Mapping[str, Any] | None = None) -> Any:
        """Run a query expected to return a single value.

        Args:
            query: Single SELECT statement returning one row and one column.
            params: Values bound to the query's named parameters.

        Returns:
            The first column of the first row, or ``None`` for an empty result.

        Raises:
            QueryTooLargeError: If the query returns more than one row.
            sqlalchemy.exc.SQLAlchemyError: If the query cannot be executed.
        """
        frame = self.read_dataframe(query, params=params, max_rows=1)
        if frame.empty:
            return None
        return frame.iloc[0, 0]

    def list_tables(self, schema: str = "geo") -> list[str]:
        """Return the table names in a schema.

        Args:
            schema: PostgreSQL schema to inspect.

        Returns:
            Table names in the schema.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If the schema cannot be inspected.
        """
        return sqlalchemy.inspect(self.db_engine).get_table_names(schema=schema)

    def close(self) -> None:
        """Dispose the engine's connection pool."""
        self.db_engine.dispose()

    @staticmethod
    def _positive_int(value: int, name: str) -> int:
        """Validate that a limit or timeout is positive.

        Args:
            value: Candidate value.
            name: Setting name used in the error message.

        Returns:
            The validated value.

        Raises:
            ValueError: If ``value`` is not positive.
        """
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")
        return value

    @staticmethod
    def _with_row_limit(query: str, max_rows: int) -> str:
        """Wrap a SELECT statement in a subquery with a row cap.

        Args:
            query: Single SELECT statement; a trailing semicolon is allowed.
            max_rows: Maximum number of rows the caller wants.

        Returns:
            A SELECT statement returning at most ``max_rows + 1`` rows, so the
            caller can detect an oversized result without fetching everything.

        Raises:
            ValueError: If the query is empty.
        """
        stripped = query.strip().rstrip(";").strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return f"SELECT * FROM ({stripped}) AS geo_visual_query LIMIT {max_rows + 1}"
