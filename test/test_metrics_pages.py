"""AppTest rendering of the natural-phenomenon metrics timeline pages."""

import datetime as dt
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard import (
    avalanche_timeline,
    drought_timeline,
    earthquake_timeline,
    fire_timeline,
    flood_timeline,
    iceberg_timeline,
    metrics_timeline,
    storm_timeline,
    volcano_timeline,
)
from dashboard.catalog import DASHBOARDS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOUNDS = (dt.date(2026, 11, 1), dt.date(2026, 11, 2))
PAGE_PATHS = {
    "avalanche": ROOT / "pages" / "1_Avalanche_Timeline.py",
    "drought": ROOT / "pages" / "2_Drought_Timeline.py",
    "earthquake": ROOT / "pages" / "3_Earthquake_Timeline.py",
    "fire": ROOT / "pages" / "4_Fire_Timeline.py",
    "flood": ROOT / "pages" / "5_Flood_Timeline.py",
    "iceberg": ROOT / "pages" / "6_Iceberg_Timeline.py",
    "storm": ROOT / "pages" / "7_Storm_Timeline.py",
    "volcano": ROOT / "pages" / "8_Volcano_Timeline.py",
}


def sample_frame(metrics: tuple[tuple[str, str | None], ...]) -> pd.DataFrame:
    """Two snapshots per metric, shaped like the dashboard query result."""
    rows = []
    for metric_name, metric_unit in metrics:
        for file_date in ("2026-11-01", "2026-11-02"):
            rows.append(
                {
                    "file_date": file_date,
                    "metric_name": metric_name,
                    "metric_unit": metric_unit,
                    "observation_count": 10,
                    "mean_value": 1.5,
                    "median_value": 1.5,
                    "max_value": 3.0,
                    "min_value": 1.0,
                    "sum_value": 6.0,
                }
            )
    frame = pd.DataFrame(rows)
    frame["file_date"] = pd.to_datetime(frame["file_date"])
    return frame


FRAMES = {
    "avalanche": sample_frame((("danger_level", "NAPADS level"), ("size", "destructive size class"))),
    "drought": sample_frame((("area", "km²"),)),
    "earthquake": sample_frame(
        (
            ("magnitude", "Mw"),
            ("depth", "km"),
            ("nst", "stations"),
        )
    ),
    "fire": sample_frame(
        (
            ("area", "km²"),
            ("geometry_count", None),
            ("percent_contained", "%"),
        )
    ),
    "flood": sample_frame(
        (
            ("baseline_days", None),
            ("discharge", "m³/s"),
            ("exceedance_ratio", None),
            ("magnitude", None),
            ("threshold", "m³/s"),
        )
    ),
    "iceberg": sample_frame(
        (
            ("geometry_count", None),
            ("surface", "N/m²"),
        )
    ),
    "storm": sample_frame(
        (
            ("direction", "degrees"),
            ("dist2land", "km"),
            ("geometry_count", None),
            ("gust", "km/h"),
            ("landfall", "km"),
            ("pressure", "mb"),
            ("speed", "km/h"),
            ("wind speed", "km/h"),
        )
    ),
    "volcano": sample_frame(
        (
            ("casualties", "people"),
            ("damage", "million USD"),
            ("magnitude", None),
            ("vei", "VEI"),
            ("vnum", "Smithsonian GVP"),
        )
    ),
}

DASHBOARDS_UNDER_TEST = [
    pytest.param(avalanche_timeline.DASHBOARD, id="avalanche"),
    pytest.param(drought_timeline.DASHBOARD, id="drought"),
    pytest.param(earthquake_timeline.DASHBOARD, id="earthquake"),
    pytest.param(fire_timeline.DASHBOARD, id="fire"),
    pytest.param(flood_timeline.DASHBOARD, id="flood"),
    pytest.param(iceberg_timeline.DASHBOARD, id="iceberg"),
    pytest.param(storm_timeline.DASHBOARD, id="storm"),
    pytest.param(volcano_timeline.DASHBOARD, id="volcano"),
]

DASHBOARD_CASES = [
    pytest.param(avalanche_timeline.DASHBOARD, 2, id="avalanche"),
    pytest.param(drought_timeline.DASHBOARD, 1, id="drought"),
    pytest.param(earthquake_timeline.DASHBOARD, 3, id="earthquake"),
    pytest.param(fire_timeline.DASHBOARD, 3, id="fire"),
    pytest.param(flood_timeline.DASHBOARD, 5, id="flood"),
    pytest.param(iceberg_timeline.DASHBOARD, 2, id="iceberg"),
    pytest.param(storm_timeline.DASHBOARD, 8, id="storm"),
    pytest.param(volcano_timeline.DASHBOARD, 5, id="volcano"),
]


def run_page(
    config: metrics_timeline.DashboardConfig,
    *,
    frame: pd.DataFrame | None = None,
    bounds: tuple[dt.date, dt.date] | None = DEFAULT_BOUNDS,
    bounds_error: Exception | None = None,
) -> AppTest:
    """Render a dashboard page with the database layer replaced by test data."""
    frame = FRAMES[config.key] if frame is None else frame
    bounds_patch = (
        patch.object(metrics_timeline, "load_date_bounds", side_effect=bounds_error)
        if bounds_error is not None
        else patch.object(metrics_timeline, "load_date_bounds", return_value=bounds)
    )
    with bounds_patch, patch.object(metrics_timeline, "load_metric_timeline", return_value=frame):
        return AppTest.from_file(str(PAGE_PATHS[config.key]), default_timeout=30).run()


@pytest.mark.parametrize("config, expected_charts", DASHBOARD_CASES)
def test_page_renders_title_charts_and_filters(
    config: metrics_timeline.DashboardConfig,
    expected_charts: int,
) -> None:
    """Each dashboard turns its metrics into charts and summarises the range."""
    at = run_page(config)

    assert not at.exception
    assert at.main.title[0].value == f"{config.page_icon} {config.page_title}"
    assert len(at.get("plotly_chart")) == expected_charts
    metric_labels = [metric.label for metric in at.metric]
    assert "Snapshots" in metric_labels
    assert "Metrics" in metric_labels
    assert "Observations" in metric_labels
    assert "Latest snapshot" in metric_labels
    metrics_by_label = {metric.label: metric.value for metric in at.metric}
    assert metrics_by_label["Metrics"] == str(expected_charts)
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
    assert any(config.view_name in caption.value for caption in at.caption)
    if config.note:
        assert any(config.note in caption.value for caption in at.caption)


def test_gap_caption_lists_missing_dates() -> None:
    """A chart with a missing snapshot gets a compact caption listing the gap."""
    frame = sample_frame((("danger_level", "NAPADS level"),)).iloc[[0]]
    at = run_page(
        avalanche_timeline.DASHBOARD,
        frame=frame,
        bounds=(dt.date(2026, 11, 1), dt.date(2026, 11, 2)),
    )

    assert not at.exception
    assert any("No observations: 2026-11-02" in caption.value for caption in at.caption)


@pytest.mark.parametrize("config", DASHBOARDS_UNDER_TEST)
def test_sidebar_keeps_navigation_and_connection_status(
    config: metrics_timeline.DashboardConfig,
) -> None:
    """The shared sidebar is available on every dashboard page."""
    at = run_page(config)

    expected_labels = ["Start", *(dashboard.nav_label for dashboard in DASHBOARDS)]
    assert [link.label for link in at.sidebar.page_link] == expected_labels
    assert [expander.label for expander in at.sidebar.expander] == ["Metric timelines"]
    assert [link.label for link in at.sidebar.expander[0].page_link] == [
        dashboard.nav_label for dashboard in DASHBOARDS
    ]
    assert any(button.label == "Recheck connection" for button in at.sidebar.button)
    assert any("not configured" in warning.value.lower() for warning in at.sidebar.warning)


@pytest.mark.parametrize("config", DASHBOARDS_UNDER_TEST)
@pytest.mark.parametrize(
    "page_kwargs, message_template, expects_date_input",
    [
        pytest.param(
            {"bounds": None},
            "No {description} are available",
            False,
            id="empty-view",
        ),
        pytest.param(
            {"frame": pd.DataFrame()},
            "No {description} were recorded",
            True,
            id="empty-range",
        ),
    ],
)
def test_empty_state_shows_a_message(
    config: metrics_timeline.DashboardConfig,
    page_kwargs: dict[str, object],
    message_template: str,
    expects_date_input: bool,
) -> None:
    """An empty view or date range is reported without rendering a chart."""
    at = run_page(config, **page_kwargs)

    expected_message = message_template.format(description=config.description)
    assert not at.exception
    assert any(expected_message in info.value for info in at.main.info)
    assert not at.get("plotly_chart")
    assert bool(at.main.date_input) is expects_date_input


@pytest.mark.parametrize("config", DASHBOARDS_UNDER_TEST)
def test_query_error_shows_a_friendly_message(
    config: metrics_timeline.DashboardConfig,
) -> None:
    """A database failure becomes an error card, not a stack trace."""
    at = run_page(config, bounds_error=RuntimeError("database unavailable"))

    expected_message = f"Could not load the {config.description} view"
    assert not at.exception
    assert any(expected_message in error.value for error in at.main.error)
