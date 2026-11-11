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


@pytest.mark.parametrize(
    "expected",
    [
        "streamlit run app.py",
        "SUPABASE_DB_USER",
        "metrics_avalanche_vw",
        "metrics_drought_vw",
        "metrics_earthquake_vw",
        "metrics_fire_vw",
        "metrics_flood_vw",
        "metrics_iceberg_vw",
        "metrics_storm_vw",
        "metrics_volcano_vw",
        "phenomenons_us_vw",
        "phenomenons_ca_vw",
        "phenomenons_cs_amer_vw",
        "phenomenons_europe_vw",
        "phenomenons_africa_vw",
        "phenomenons_asia_vw",
        "phenomenons_aus_oc_vw",
        "phenomenons_ru_vw",
        "phenomenons_waters_vw",
    ],
)
def test_readme_documents_streamlit_supabase_and_dashboards(expected: str) -> None:
    """The README explains how to run the app, configure Supabase and find the dashboards."""
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
        "pages/2_Drought_Timeline.py",
        "pages/3_Earthquake_Timeline.py",
        "pages/4_Fire_Timeline.py",
        "pages/5_Flood_Timeline.py",
        "pages/6_Iceberg_Timeline.py",
        "pages/7_Storm_Timeline.py",
        "pages/8_Volcano_Timeline.py",
        "pages/9_United_States_Map.py",
        "pages/10_Canada_Map.py",
        "pages/11_Central_South_America_Map.py",
        "pages/12_Europe_Map.py",
        "pages/13_Africa_Map.py",
        "pages/14_Asia_Map.py",
        "pages/15_Australia_Oceania_Map.py",
        "pages/16_Russia_Map.py",
        "pages/17_International_Waters_Map.py",
        "dashboard/avalanche_timeline.py",
        "dashboard/drought_timeline.py",
        "dashboard/earthquake_timeline.py",
        "dashboard/fire_timeline.py",
        "dashboard/flood_timeline.py",
        "dashboard/iceberg_timeline.py",
        "dashboard/storm_timeline.py",
        "dashboard/volcano_timeline.py",
        "dashboard/metrics_timeline.py",
        "dashboard/phenomenon_map.py",
        "dashboard/map_configs.py",
        "dashboard/catalog.py",
        "dashboard/__init__.py",
        "docs/avalanche-timeline.md",
        "docs/drought-timeline.md",
        "docs/earthquake-timeline.md",
        "docs/phenomena-timelines.md",
        "docs/phenomenon-maps.md",
        "sql/avalanche_metrics_date_bounds.sql",
        "sql/avalanche_metrics_timeline.sql",
        "sql/drought_metrics_date_bounds.sql",
        "sql/drought_metrics_timeline.sql",
        "sql/earthquake_metrics_date_bounds.sql",
        "sql/earthquake_metrics_timeline.sql",
        "sql/fire_metrics_date_bounds.sql",
        "sql/fire_metrics_timeline.sql",
        "sql/flood_metrics_date_bounds.sql",
        "sql/flood_metrics_timeline.sql",
        "sql/iceberg_metrics_date_bounds.sql",
        "sql/iceberg_metrics_timeline.sql",
        "sql/storm_metrics_date_bounds.sql",
        "sql/storm_metrics_timeline.sql",
        "sql/volcano_metrics_date_bounds.sql",
        "sql/volcano_metrics_timeline.sql",
        "sql/metrics_distribution.sql",
        "sql/phenomenons_map.sql",
        "sql/phenomenons_map_date_bounds.sql",
        "test/test_metrics_pages.py",
        "test/dashboard/test_dashboard_configs.py",
        "test/dashboard/test_metrics_timeline.py",
        "test/test_phenomenon_map.py",
        "utils/layout.py",
        "utils/sql.py",
    ],
)
def test_dashboard_files_are_committed(relative_path: str) -> None:
    """The dashboards, SQL scripts, docs and shared helpers are part of the runtime."""
    assert (ROOT / relative_path).is_file()
