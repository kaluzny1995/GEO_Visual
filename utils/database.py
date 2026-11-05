"""Streamlit-facing Supabase helpers."""

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from model.config.app_config import AppConfig
from model.config.supabase_config import SupabaseConnectionConfig
from provider.supabase_postgres.supabase_postgres_provider import SupabasePostgresProvider

logger = logging.getLogger(__name__)

# How long the welcome page reuses a connection check before probing again.
STATUS_TTL_SECONDS = 60

# Loaded once per process; a config change requires a Streamlit restart.
_DB_CONFIG = AppConfig.from_json().database


@dataclass(frozen=True)
class ConnectionStatus:
    """Result of a Supabase connection check.

    Attributes:
        connected: Whether the database answered ``SELECT 1``.
        message: Short message suitable for the Streamlit sidebar.
    """

    connected: bool
    message: str


@st.cache_resource(show_spinner=False)
def get_provider() -> SupabasePostgresProvider:
    """Return the process-wide provider, creating it on first use.

    The engine is cached for the lifetime of the Streamlit process so every
    rerun and page reuses the same connection pool.

    Returns:
        The shared :class:`SupabasePostgresProvider`.
    """
    return SupabasePostgresProvider(
        connect_timeout=_DB_CONFIG.connect_timeout,
        pool_size=_DB_CONFIG.pool_size,
        max_overflow=_DB_CONFIG.max_overflow,
        pool_recycle=_DB_CONFIG.pool_recycle_seconds,
        max_rows=_DB_CONFIG.max_rows,
        statement_timeout_ms=_DB_CONFIG.statement_timeout_ms,
    )


def check_connection() -> ConnectionStatus:
    """Check whether Supabase is configured and reachable.

    Missing credentials are reported without raising, so the welcome page can
    render before ``.env`` has been created. Connection errors are logged and
    reported with a short message; the exception is not shown in the UI.

    Returns:
        A :class:`ConnectionStatus` describing the result.
    """
    try:
        SupabaseConnectionConfig.from_env()
    except ValueError as exc:
        logger.info("Supabase credentials are not configured: %s", exc)
        return ConnectionStatus(
            connected=False,
            message="Supabase is not configured. Copy .env.example to .env and fill in SUPABASE_DB_*.",
        )

    try:
        get_provider().connect()
    except Exception as exc:  # UI boundary: any failure becomes a sidebar message.
        logger.warning("Supabase connection failed: %s", exc)
        return ConnectionStatus(
            connected=False,
            message="Could not connect to Supabase. Check your credentials and network.",
        )

    return ConnectionStatus(connected=True, message="Connected to Supabase")


@st.cache_data(ttl=STATUS_TTL_SECONDS, show_spinner=False)
def cached_connection_status() -> ConnectionStatus:
    """Return a connection status cached for ``STATUS_TTL_SECONDS``.

    Returns:
        The cached :class:`ConnectionStatus`.
    """
    return check_connection()


@st.cache_data(
    ttl=_DB_CONFIG.cache_ttl_seconds,
    max_entries=_DB_CONFIG.cache_max_entries,
    show_spinner="Loading data from Supabase...",
)
def cached_query(
    query: str,
    params: tuple[tuple[str, Any], ...] = (),
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Run a guarded query and cache the (small) result.

    Use this for dashboard data, not for raw table dumps: the provider caps
    rows and enforces a statement timeout, and the cache is bounded by
    ``cache_ttl_seconds`` / ``cache_max_entries`` in ``config.json``.

    Args:
        query: Single SELECT statement with optional ``:named`` parameters.
        params: Named parameters as hashable ``(name, value)`` pairs, so
            Streamlit can build a stable cache key.
        max_rows: Optional per-query row cap; defaults to the provider cap.

    Returns:
        The query result as a pandas DataFrame.
    """
    return get_provider().read_dataframe(query, dict(params), max_rows=max_rows)


def clear_connection_cache() -> None:
    """Drop the cached provider, connection status and query results.

    Called by the sidebar's "Recheck connection" button so a corrected
    ``.env`` is picked up without restarting Streamlit.
    """
    get_provider.clear()
    cached_connection_status.clear()
    cached_query.clear()
