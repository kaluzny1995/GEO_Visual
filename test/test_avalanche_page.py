"""AppTest rendering of the avalanche metrics timeline page."""

import datetime as dt
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard import avalanche_timeline as timeline

PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "1_Avalanche_Timeline.py"


def sample_frame() -> pd.DataFrame:
    """Two snapshots for two metrics, shaped like the dashboard query result."""
    return pd.DataFrame(
        {
            "file_date": pd.to_datetime(["2026-11-01", "2026-11-02", "2026-11-01", "2026-11-02"]),
            "metric_name": ["danger_level", "danger_level", "size", "size"],
            "metric_unit": ["NAPADS level", "NAPADS level", "destructive size class", "destructive size class"],
            "observation_count": [10, 12, 4, 5],
            "mean_value": [1.5, 2.0, 1.5, 1.75],
            "median_value": [1.5, 1.75, 1.5, 1.75],
            "max_value": [3.0, 4.0, 2.0, 2.0],
            "min_value": [1.0, 1.0, 1.5, 1.5],
            "sum_value": [6.0, 12.0, 6.0, 8.75],
        }
    )


def run_page(
    *,
    bounds: tuple[dt.date, dt.date] | None = (dt.date(2026, 11, 1), dt.date(2026, 11, 2)),
    frame: pd.DataFrame | None = None,
    bounds_error: Exception | None = None,
) -> AppTest:
    """Render the page with the database layer replaced by test data."""
    frame = sample_frame() if frame is None else frame
    bounds_patch = (
        patch.object(timeline, "load_date_bounds", side_effect=bounds_error)
        if bounds_error is not None
        else patch.object(timeline, "load_date_bounds", return_value=bounds)
    )
    with bounds_patch, patch.object(timeline, "load_metric_timeline", return_value=frame):
        return AppTest.from_file(str(PAGE_PATH), default_timeout=30).run()


def test_renders_one_chart_per_metric_with_kpis() -> None:
    """The page turns each metric into its own timeline and summarises the range."""
    at = run_page()

    assert not at.exception
    assert at.main.title[0].value == f"{timeline.PAGE_ICON} {timeline.PAGE_TITLE}"
    assert len(at.get("plotly_chart")) == 2
    metric_labels = [metric.label for metric in at.metric]
    assert "Snapshots" in metric_labels
    assert "Metrics" in metric_labels
    assert "Observations" in metric_labels
    assert "Latest snapshot" in metric_labels
    assert list(at.main.selectbox[0].options) == [
        "Mean",
        "Median",
        "Maximum",
        "Total",
        "Observations",
    ]
    assert any("Mean of all recorded values" in caption.value for caption in at.caption)
    assert any("each chart spans the selected dates" in caption.value for caption in at.caption)
    assert any("shaded areas mark missing observations" in caption.value for caption in at.caption)
    assert any("danger_level = -1" in caption.value for caption in at.caption)


def test_sidebar_keeps_branding_and_connection_status() -> None:
    """The shared sidebar is available on dashboard pages too."""
    at = run_page()

    assert [link.label for link in at.sidebar.page_link] == ["Start", "Avalanche Timeline"]
    assert any(button.label == "Recheck connection" for button in at.sidebar.button)
    assert any("not configured" in warning.value.lower() for warning in at.sidebar.warning)


@pytest.mark.parametrize(
    "page_kwargs, expected_message, expects_date_input",
    [
        pytest.param(
            {"bounds": None},
            "No avalanche metrics are available",
            False,
            id="empty-view",
        ),
        pytest.param(
            {"frame": pd.DataFrame()},
            "No avalanche metrics were recorded",
            True,
            id="empty-range",
        ),
    ],
)
def test_empty_state_shows_a_message(
    page_kwargs: dict[str, object],
    expected_message: str,
    expects_date_input: bool,
) -> None:
    """An empty view or date range is reported without rendering a chart."""
    at = run_page(**page_kwargs)

    assert not at.exception
    assert any(expected_message in info.value for info in at.main.info)
    assert not at.get("plotly_chart")
    assert bool(at.main.date_input) is expects_date_input


def test_query_error_shows_a_friendly_message() -> None:
    """A database failure becomes an error card, not a stack trace."""
    at = run_page(bounds_error=RuntimeError("database unavailable"))

    assert not at.exception
    assert any("Could not load the avalanche metrics view" in error.value for error in at.main.error)
