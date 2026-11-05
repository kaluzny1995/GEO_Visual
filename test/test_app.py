"""Tests for the Streamlit welcome page, rendered with Streamlit's AppTest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from model.config.app_config import AppConfig

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def run_app() -> AppTest:
    """Render ``app.py`` in Streamlit's test runtime."""
    return AppTest.from_file(str(APP_PATH), default_timeout=30).run()


def test_main_area_contains_only_title_and_description() -> None:
    """The main area contains exactly the title and its description."""
    config = AppConfig.from_json()
    at = run_app()

    assert not at.exception
    assert len(at.main.title) == 1
    assert at.main.title[0].value == f"{config.app.page_icon} {config.app.title}"
    assert len(at.main.markdown) == 1
    assert at.main.markdown[0].value == config.app.subtitle

    assert not at.main.subheader
    assert not at.main.button
    assert not at.main.code
    assert not at.main.warning


def test_sidebar_has_branding_and_connection_status() -> None:
    """The left sidebar keeps branding and the Supabase connection status."""
    config = AppConfig.from_json()
    at = run_app()

    assert any(title.value == f"{config.app.page_icon} {config.app.title}" for title in at.sidebar.title)
    assert any(button.label == "Recheck connection" for button in at.sidebar.button)
    assert any("not configured" in warning.value.lower() for warning in at.sidebar.warning)
