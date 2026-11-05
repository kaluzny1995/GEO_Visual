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


@pytest.mark.parametrize("expected", ["streamlit run app.py", "SUPABASE_DB_USER"])
def test_readme_documents_streamlit_and_supabase_setup(expected: str) -> None:
    """The README explains how to run the app and configure Supabase."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert expected in text


def test_streamlit_theme_is_committed() -> None:
    """The shared Streamlit theme lives in ``.streamlit/config.toml``."""
    assert (ROOT / ".streamlit" / "config.toml").is_file()
