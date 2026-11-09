"""Tests for the Streamlit welcome page, rendered with Streamlit's AppTest."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from dashboard.catalog import DASHBOARDS, DashboardCard
from model.config.app_config import AppConfig

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def run_app() -> AppTest:
    """Render ``app.py`` in Streamlit's test runtime."""
    return AppTest.from_file(str(APP_PATH), default_timeout=30).run()


def test_main_area_contains_the_welcome_header() -> None:
    """The main area describes the project and lists the dashboards."""
    config = AppConfig.from_json()
    at = run_app()

    assert not at.exception
    assert len(at.main.title) == 1
    assert at.main.title[0].value == f"{config.app.page_icon} {config.app.title}"
    assert config.app.subtitle in [markdown.value for markdown in at.main.markdown]
    assert [subheader.value for subheader in at.main.subheader] == ["Dashboards"]
    assert [link.label for link in at.main.page_link] == [f"Open {dashboard.title}" for dashboard in DASHBOARDS]

    assert not at.main.button
    assert not at.main.code
    assert not at.main.warning


@pytest.mark.parametrize("dashboard", DASHBOARDS, ids=lambda dashboard: dashboard.nav_label)
def test_main_area_contains_each_dashboard_card(dashboard: DashboardCard) -> None:
    """Every configured dashboard gets a welcome card and an open link."""
    at = run_app()
    markdown_values = [markdown.value for markdown in at.main.markdown]

    assert f"#### {dashboard.icon} {dashboard.title}" in markdown_values
    assert dashboard.description in markdown_values
    assert any(link.label == f"Open {dashboard.title}" for link in at.main.page_link)


def test_sidebar_has_branding_navigation_and_connection_status() -> None:
    """The left sidebar keeps branding, the Start tab and the dashboard links."""
    config = AppConfig.from_json()
    at = run_app()

    assert any(title.value == f"{config.app.page_icon} {config.app.title}" for title in at.sidebar.title)
    assert [link.label for link in at.sidebar.page_link] == [
        "Start",
        *(dashboard.nav_label for dashboard in DASHBOARDS),
    ]
    assert [expander.label for expander in at.sidebar.expander] == ["Metric timelines and distributions"]
    assert [link.label for link in at.sidebar.expander[0].page_link] == [
        dashboard.nav_label for dashboard in DASHBOARDS
    ]
    assert at.sidebar.page_link[0].page == "app"
    assert any(button.label == "Recheck connection" for button in at.sidebar.button)
    assert any("not configured" in warning.value.lower() for warning in at.sidebar.warning)
