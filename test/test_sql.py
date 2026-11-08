"""Tests for the parametrized SQL scripts and their loader."""

import pytest

from dashboard import (
    avalanche_timeline,
    drought_timeline,
    earthquake_timeline,
    fire_timeline,
    flood_timeline,
    iceberg_timeline,
    storm_timeline,
    volcano_timeline,
)
from dashboard.metrics_timeline import DashboardConfig
from utils import sql

ALL_DASHBOARDS = (
    avalanche_timeline.DASHBOARD,
    drought_timeline.DASHBOARD,
    earthquake_timeline.DASHBOARD,
    fire_timeline.DASHBOARD,
    flood_timeline.DASHBOARD,
    iceberg_timeline.DASHBOARD,
    storm_timeline.DASHBOARD,
    volcano_timeline.DASHBOARD,
)

DASHBOARD_CONFIGS = [pytest.param(config, id=config.key) for config in ALL_DASHBOARDS]

SQL_FILE_CASES = [
    pytest.param(
        f"{config.key}_metrics_date_bounds",
        ("to_char(min(file_date)", "to_char(max(file_date)", config.view_name),
        id=f"{config.key}-date-bounds",
    )
    for config in ALL_DASHBOARDS
]
SQL_FILE_CASES += [
    pytest.param(
        f"{config.key}_metrics_timeline",
        (
            ":start_date",
            ":end_date",
            "GROUP BY file_date",
            "percentile_cont(0.5)",
            config.view_name,
        ),
        id=f"{config.key}-timeline",
    )
    for config in ALL_DASHBOARDS
]


@pytest.mark.parametrize("name, fragments", SQL_FILE_CASES)
def test_sql_file_contains_required_fragments(name: str, fragments: tuple[str, ...]) -> None:
    """Each dashboard query lives in a reviewable SQL file with its parameters."""
    text = sql.load_sql(name)
    for fragment in fragments:
        assert fragment in text


@pytest.mark.parametrize("config", DASHBOARD_CONFIGS)
@pytest.mark.parametrize(
    "attribute, file_template",
    [
        pytest.param("date_bounds_query", "{key}_metrics_date_bounds", id="date-bounds"),
        pytest.param("timeline_query", "{key}_metrics_timeline", id="timeline"),
    ],
)
def test_dashboard_queries_are_loaded_from_sql_files(
    config: DashboardConfig,
    attribute: str,
    file_template: str,
) -> None:
    """The dashboards use the checked-in SQL files, not inline query strings."""
    assert getattr(config, attribute) == sql.load_sql(file_template.format(key=config.key))


@pytest.mark.parametrize("name", ["does_not_exist", ""])
def test_load_sql_raises_for_missing_scripts(name: str) -> None:
    """A missing script fails loudly instead of returning an empty query."""
    with pytest.raises(FileNotFoundError):
        sql.load_sql(name)
