"""Tests for the application configuration (``config.json``)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from model.config.app_config import AppConfig

VALID_CONFIG = {
    "app": {
        "title": "GEO Visual",
        "subtitle": "Interactive dashboards for the GEO geographic-data pipeline",
        "page_icon": "🌍",
        "layout": "wide",
        "version": "0.1.0",
    },
    "database": {
        "db_schema": "geo",
        "connect_timeout": 10,
        "pool_size": 5,
        "max_overflow": 5,
    },
}

DEFAULT_DATABASE = {
    "db_schema": "geo",
    "connect_timeout": 10,
    "pool_size": 5,
    "max_overflow": 5,
    "pool_recycle_seconds": 300,
    "max_rows": 50_000,
    "statement_timeout_ms": 30_000,
    "cache_ttl_seconds": 300,
    "cache_max_entries": 32,
}

CUSTOM_DATABASE = {
    "db_schema": "geo",
    "connect_timeout": 7,
    "pool_size": 3,
    "max_overflow": 2,
    "pool_recycle_seconds": 120,
    "max_rows": 1_000,
    "statement_timeout_ms": 5_000,
    "cache_ttl_seconds": 60,
    "cache_max_entries": 8,
}

DATABASE_CASES = [
    pytest.param({"db_schema": "geo"}, DEFAULT_DATABASE, id="defaults"),
    pytest.param(CUSTOM_DATABASE, CUSTOM_DATABASE, id="custom"),
]


class TestAppConfig:
    """Tests for :class:`AppConfig`."""

    def test_from_json(self, tmp_path: Path) -> None:
        """``from_json`` reads the app and database sections."""
        path = tmp_path / "config.json"
        path.write_text(json.dumps(VALID_CONFIG))
        cfg = AppConfig.from_json(path=str(path))
        assert cfg.app.title == "GEO Visual"
        assert cfg.app.layout == "wide"
        assert cfg.database.db_schema == "geo"
        assert cfg.database.connect_timeout == 10

    def test_frozen(self, tmp_path: Path) -> None:
        """The config model is immutable (frozen)."""
        path = tmp_path / "config.json"
        path.write_text(json.dumps(VALID_CONFIG))
        cfg = AppConfig.from_json(path=str(path))
        with pytest.raises(ValidationError):
            cfg.app.title = "other"

    @pytest.mark.parametrize("database_settings, expected", DATABASE_CASES)
    def test_database_settings(
        self,
        tmp_path: Path,
        database_settings: dict[str, object],
        expected: dict[str, object],
    ) -> None:
        """Database settings load from ``config.json`` and fall back to defaults."""
        config = {"app": VALID_CONFIG["app"], "database": database_settings}
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        cfg = AppConfig.from_json(path=str(path))
        for field, value in expected.items():
            assert getattr(cfg.database, field) == value

    @pytest.mark.parametrize("layout", ["fullscreen", "sidebar", ""])
    def test_unsupported_layout_is_rejected(self, tmp_path: Path, layout: str) -> None:
        """Only Streamlit's supported layouts are accepted."""
        config = json.loads(json.dumps(VALID_CONFIG))
        config["app"]["layout"] = layout
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        with pytest.raises(ValidationError):
            AppConfig.from_json(path=str(path))

    def test_project_config_json_is_valid(self) -> None:
        """The project's ``config.json`` parses into a valid config."""
        cfg = AppConfig.from_json()
        assert cfg.app.title == "GEO Visual"
        assert cfg.database.db_schema == "geo"
        assert cfg.app.version
