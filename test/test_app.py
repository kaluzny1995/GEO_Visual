"""Tests for the Streamlit welcome page, rendered with Streamlit's AppTest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def run_app() -> AppTest:
    """Render ``app.py`` in Streamlit's test runtime."""
    return AppTest.from_file(str(APP_PATH), default_timeout=30).run()


def test_welcome_page_renders_without_a_database() -> None:
    """The welcome page renders even when Supabase is not configured."""
    at = run_app()
    assert not at.exception
    assert at.title[0].value == "🌍 GEO Visual"
    assert any("Interactive dashboards" in block.value for block in at.markdown)
    assert any("Explore datasets" in block.value for block in at.subheader)
    assert any("not configured" in warning.value.lower() for warning in at.warning)


def test_sidebar_exposes_connection_recheck() -> None:
    """The sidebar offers a connection recheck button and pipeline links."""
    at = run_app()
    assert any(button.label == "Recheck connection" for button in at.button)
    assert any("GEO_ETL" in block.value for block in at.markdown)


def test_quick_start_shows_the_streamlit_command() -> None:
    """The quick-start block documents how to launch the app."""
    at = run_app()
    assert any("streamlit run app.py" in block.value for block in at.code)
