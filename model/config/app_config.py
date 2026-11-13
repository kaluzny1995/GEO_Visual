"""Streamlit application configuration (``config.json``)."""

import json
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")


class AppSection(BaseModel):
    """Welcome-page settings.

    Attributes:
        title: Application title shown in the page header and browser tab.
        subtitle: One-line description shown under the title.
        page_icon: Emoji or icon used by Streamlit.
        layout: Streamlit page layout.
        version: Displayed application version.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    subtitle: str
    page_icon: str
    layout: Literal["centered", "wide"] = "wide"
    version: str


class DatabaseSection(BaseModel):
    """Database settings used by the Streamlit data layer.

    Attributes:
        db_schema: PostgreSQL schema that holds the GEO tables.
        connect_timeout: Seconds before a connection attempt gives up.
        pool_size: Number of connections kept in the SQLAlchemy pool.
        max_overflow: Extra connections allowed above ``pool_size``.
        pool_recycle_seconds: Recycle pooled connections after this many seconds.
        max_rows: Default row cap for a single dataframe query.
        statement_timeout_ms: Per-query PostgreSQL statement timeout.
        cache_ttl_seconds: How long Streamlit caches query results.
        cache_max_entries: Maximum number of cached query results.
        connection_status_ttl_seconds: Sidebar connection-status cache lifetime.
        distribution_max_rows: Row cap for the timeline histogram query.
        map_max_rows: Row cap for an area-map POI query.
        map_default_min_magnitude: Initial earthquake magnitude filter on maps.
    """

    model_config = ConfigDict(frozen=True)

    db_schema: str = "geo"
    connect_timeout: int = 10
    pool_size: int = 5
    max_overflow: int = 5
    pool_recycle_seconds: int = 300
    max_rows: int = 50_000
    statement_timeout_ms: int = 30_000
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 32
    connection_status_ttl_seconds: int = 60
    distribution_max_rows: int = 250_000
    map_max_rows: int = 50_000
    map_default_min_magnitude: float = 2.5


class AppConfig(BaseModel):
    """Top-level ``config.json`` model.

    Attributes:
        app: Welcome-page settings.
        database: Database settings.
    """

    model_config = ConfigDict(frozen=True)

    app: AppSection
    database: DatabaseSection

    @staticmethod
    def from_json(path: str | None = None) -> "AppConfig":
        """Load the application configuration from a JSON file.

        Args:
            path: Path to the config file. Defaults to ``config.json``
                in the project root.

        Returns:
            A frozen :class:`AppConfig` instance.
        """
        if path is None:
            path = CONFIG_PATH
        with open(path, encoding="utf-8") as f:
            return AppConfig(**json.load(f))
