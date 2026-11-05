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

    def test_database_defaults(self, tmp_path: Path) -> None:
        """Omitted database settings fall back to the documented defaults."""
        config = {"app": VALID_CONFIG["app"], "database": {"db_schema": "geo"}}
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        cfg = AppConfig.from_json(path=str(path))
        assert cfg.database.connect_timeout == 10
        assert cfg.database.pool_size == 5
        assert cfg.database.max_overflow == 5
        assert cfg.database.pool_recycle_seconds == 300
        assert cfg.database.max_rows == 50_000
        assert cfg.database.statement_timeout_ms == 30_000
        assert cfg.database.cache_ttl_seconds == 300
        assert cfg.database.cache_max_entries == 32

    def test_database_performance_settings_are_loaded(self, tmp_path: Path) -> None:
        """Row, timeout and cache limits can be tuned in ``config.json``."""
        config = json.loads(json.dumps(VALID_CONFIG))
        config["database"].update(
            {
                "max_rows": 1_000,
                "statement_timeout_ms": 5_000,
                "cache_ttl_seconds": 60,
                "cache_max_entries": 8,
                "pool_recycle_seconds": 120,
            }
        )
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        cfg = AppConfig.from_json(path=str(path))
        assert cfg.database.max_rows == 1_000
        assert cfg.database.statement_timeout_ms == 5_000
        assert cfg.database.cache_ttl_seconds == 60
        assert cfg.database.cache_max_entries == 8
        assert cfg.database.pool_recycle_seconds == 120

    def test_unsupported_layout_is_rejected(self, tmp_path: Path) -> None:
        """Only Streamlit's supported layouts are accepted."""
        config = json.loads(json.dumps(VALID_CONFIG))
        config["app"]["layout"] = "fullscreen"
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
