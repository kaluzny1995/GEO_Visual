"""Tests for the Streamlit welcome page, rendered with Streamlit's AppTest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from model.config.app_config import AppConfig

APP_PATH = Path(__file__).resolve().parents[1] / "Start.py"


def run_app() -> AppTest:
    """Render ``Start.py`` in Streamlit's test runtime."""
    return AppTest.from_file(str(APP_PATH), default_timeout=30).run()


def test_main_area_contains_welcome_and_avalanche_dashboard_card() -> None:
    """The main area describes the project and links to the avalanche dashboard."""
    config = AppConfig.from_json()
    at = run_app()

    assert not at.exception
    assert len(at.main.title) == 1
    assert at.main.title[0].value == f"{config.app.page_icon} {config.app.title}"

    markdown_values = [markdown.value for markdown in at.main.markdown]
    assert config.app.subtitle in markdown_values
    assert "#### ❄️ Avalanche metrics timeline" in markdown_values
    assert any("geo.metrics_avalanche_vw" in value for value in markdown_values)

    assert [subheader.value for subheader in at.main.subheader] == ["Dashboards"]
    assert [link.label for link in at.main.page_link] == ["Open Avalanche metrics timeline"]
    assert at.main.page_link[0].page == "Avalanche_Timeline"

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
