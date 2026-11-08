"""Repository contract tests — keep the GitHub-facing files in sync."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("expected", ["name: geo_visual_311", "python=3.11"])
def test_environment_yml_declares_the_geo_visual_311_environment(expected: str) -> None:
    """The conda environment is named ``geo_visual_311`` and pins Python 3.11."""
    text = (ROOT / "environment.yml").read_text(encoding="utf-8")
    assert expected in text


@pytest.mark.parametrize("expected", [".env", "!.env.example"])
def test_gitignore_ignores_secrets_but_keeps_the_template(expected: str) -> None:
    """``.env`` is ignored while ``.env.example`` stays committed."""
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert expected in lines


@pytest.mark.parametrize("env", ["lint", "format", "format-fix", "typecheck", "warnings"])
def test_tox_defines_the_quality_environments(env: str) -> None:
    """tox exposes lint, format, typecheck and warnings environments."""
    text = (ROOT / "tox.ini").read_text(encoding="utf-8")
    assert f"[testenv:{env}]" in text


@pytest.mark.parametrize("expected", ["streamlit run app.py", "SUPABASE_DB_USER", "metrics_avalanche_vw"])
def test_readme_documents_streamlit_and_supabase_setup(expected: str) -> None:
    """The README explains how to run the app, configure Supabase and find the dashboard."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert expected in text


def test_streamlit_theme_is_dark_and_committed() -> None:
    """The shared Streamlit theme lives in ``.streamlit/config.toml`` and is dark."""
    theme = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'base = "dark"' in theme
    assert 'backgroundColor = "#0f172a"' in theme
    assert 'textColor = "#e2e8f0"' in theme
    assert "chartCategoricalColors" in theme


@pytest.mark.parametrize(
    "relative_path",
    [
        "pages/1_Avalanche_Timeline.py",
        "dashboard/avalanche_timeline.py",
        "dashboard/__init__.py",
        "sql/avalanche_metrics_date_bounds.sql",
        "sql/avalanche_metrics_timeline.sql",
        "utils/layout.py",
        "utils/sql.py",
    ],
)
def test_first_dashboard_files_are_committed(relative_path: str) -> None:
    """The avalanche timeline page, SQL scripts and shared helpers are part of the runtime."""
    assert (ROOT / relative_path).is_file()
