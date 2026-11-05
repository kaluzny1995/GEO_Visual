"""Repository contract tests — keep the GitHub-facing files in sync."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_environment_yml_declares_the_geo_visual_311_environment() -> None:
    """The conda environment is named ``geo_visual_311`` and pins Python 3.11."""
    text = (ROOT / "environment.yml").read_text(encoding="utf-8")
    assert "name: geo_visual_311" in text
    assert "python=3.11" in text


def test_gitignore_ignores_secrets_but_keeps_the_template() -> None:
    """``.env`` is ignored while ``.env.example`` stays committed."""
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in lines
    assert "!.env.example" in lines


def test_tox_defines_the_quality_environments() -> None:
    """tox exposes lint, format, typecheck and warnings environments."""
    text = (ROOT / "tox.ini").read_text(encoding="utf-8")
    for env in ("lint", "format", "format-fix", "typecheck", "warnings"):
        assert f"[testenv:{env}]" in text


def test_readme_documents_streamlit_and_supabase_setup() -> None:
    """The README explains how to run the app and configure Supabase."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "streamlit run app.py" in text
    assert "SUPABASE_DB_USER" in text


def test_streamlit_theme_is_committed() -> None:
    """The shared Streamlit theme lives in ``.streamlit/config.toml``."""
    assert (ROOT / ".streamlit" / "config.toml").is_file()
