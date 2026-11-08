"""Tests for the parametrized SQL scripts and their loader."""

import pytest

from dashboard import avalanche_timeline as timeline
from utils import sql


@pytest.mark.parametrize(
    "name, fragments",
    [
        pytest.param(
            "avalanche_metrics_date_bounds",
            ("to_char(min(file_date)", "to_char(max(file_date)", "geo.metrics_avalanche_vw"),
            id="date-bounds",
        ),
        pytest.param(
            "avalanche_metrics_timeline",
            (
                ":start_date",
                ":end_date",
                "GROUP BY file_date",
                "percentile_cont(0.5)",
                "geo.metrics_avalanche_vw",
            ),
            id="timeline",
        ),
    ],
)
def test_sql_file_contains_required_fragments(name: str, fragments: tuple[str, ...]) -> None:
    """Each dashboard query lives in a reviewable SQL file with its parameters."""
    text = sql.load_sql(name)
    for fragment in fragments:
        assert fragment in text


@pytest.mark.parametrize(
    "constant, file_name",
    [
        pytest.param(timeline.DATE_BOUNDS_QUERY, "avalanche_metrics_date_bounds", id="date-bounds"),
        pytest.param(timeline.TIMELINE_QUERY, "avalanche_metrics_timeline", id="timeline"),
    ],
)
def test_dashboard_constants_are_loaded_from_sql_files(constant: str, file_name: str) -> None:
    """The dashboard uses the checked-in SQL files, not inline query strings."""
    assert constant == sql.load_sql(file_name)


@pytest.mark.parametrize("name", ["does_not_exist", ""])
def test_load_sql_raises_for_missing_scripts(name: str) -> None:
    """A missing script fails loudly instead of returning an empty query."""
    with pytest.raises(FileNotFoundError):
        sql.load_sql(name)
