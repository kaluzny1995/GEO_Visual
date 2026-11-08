"""Tests for the avalanche, drought and earthquake dashboard configurations."""

import datetime as dt
from unittest.mock import patch

import pandas as pd
import pytest

from dashboard import avalanche_timeline, drought_timeline, earthquake_timeline, metrics_timeline

DASHBOARDS = [
    pytest.param(avalanche_timeline.DASHBOARD, id="avalanche"),
    pytest.param(drought_timeline.DASHBOARD, id="drought"),
    pytest.param(earthquake_timeline.DASHBOARD, id="earthquake"),
]


def sample_frame() -> pd.DataFrame:
    """Two daily snapshots, already aggregated by SQL."""
    return pd.DataFrame(
        {
            "file_date": pd.to_datetime(["2026-11-01", "2026-11-02"]),
            "metric_name": ["area", "area"],
            "metric_unit": ["km²", "km²"],
            "observation_count": [10, 12],
            "mean_value": [1.5, 2.0],
            "median_value": [1.5, 1.75],
            "max_value": [3.0, 4.0],
            "min_value": [1.0, 1.5],
            "sum_value": [6.0, 12.0],
        }
    )


def frame_for_metrics(metrics: tuple[tuple[str, str], ...]) -> pd.DataFrame:
    """Build an aggregated frame with one two-row series per metric pair."""
    frames = []
    for metric_name, metric_unit in metrics:
        frames.append(sample_frame().assign(metric_name=metric_name, metric_unit=metric_unit))
    return pd.concat(frames, ignore_index=True)


def test_earthquake_config_declares_the_hidden_mlr_scale() -> None:
    """The sparse mlr magnitude scale is explicitly hidden in configuration."""
    assert earthquake_timeline.DASHBOARD.hidden_metrics == (("magnitude", "mlr"),)


def test_earthquake_hides_the_sparse_mlr_magnitude_series() -> None:
    """The earthquake dashboard drops the one-observation mlr magnitude scale."""
    frame = frame_for_metrics(
        (
            ("magnitude", "Mw"),
            ("magnitude", "mlr"),
            ("depth", "km"),
            ("nst", "stations"),
        )
    )
    with patch.object(metrics_timeline, "cached_query", return_value=frame):
        result = metrics_timeline.load_metric_timeline(
            earthquake_timeline.DASHBOARD,
            dt.date(2026, 11, 1),
            dt.date(2026, 11, 2),
        )

    assert set(metrics_timeline.metric_groups(result)) == {
        ("magnitude", "Mw"),
        ("depth", "km"),
        ("nst", "stations"),
    }


@pytest.mark.parametrize("config", DASHBOARDS)
class TestDashboardConfig:
    """Tests for each configured dashboard."""

    def test_metadata_is_complete(self, config: metrics_timeline.DashboardConfig) -> None:
        """Every dashboard has a key, view, page title, icon and description."""
        assert config.key
        assert config.view_name.startswith("geo.metrics_")
        assert config.page_title
        assert config.page_icon
        assert "metrics" in config.description

    def test_sql_queries_reference_the_configured_view(self, config: metrics_timeline.DashboardConfig) -> None:
        """Both SQL scripts read the dashboard's own view."""
        assert config.view_name in config.date_bounds_query
        assert config.view_name in config.timeline_query
        assert "event_category = " in config.timeline_query

    def test_timeline_query_keeps_every_recorded_value(self, config: metrics_timeline.DashboardConfig) -> None:
        """The aggregates must not filter out encoded states such as ``-1``."""
        assert "FILTER (WHERE metric_value" not in config.timeline_query
        assert "avg(metric_value) AS mean_value" in config.timeline_query
        assert "percentile_cont(0.5) WITHIN GROUP (ORDER BY metric_value) AS median_value" in config.timeline_query


@pytest.mark.parametrize("config", DASHBOARDS)
class TestLoadDateBounds:
    """Tests for :func:`metrics_timeline.load_date_bounds`."""

    def test_returns_first_and_last_snapshot_date(self, config: metrics_timeline.DashboardConfig) -> None:
        """The bounds query narrows the date picker to the available snapshots."""
        result = pd.DataFrame({"min_date": ["2026-09-01"], "max_date": ["2026-11-06"]})
        with patch.object(metrics_timeline, "cached_query", return_value=result) as query:
            bounds = metrics_timeline.load_date_bounds(config)

        assert bounds == (dt.date(2026, 9, 1), dt.date(2026, 11, 6))
        query.assert_called_once_with(config.date_bounds_query)

    @pytest.mark.parametrize(
        "frame",
        [
            pytest.param(pd.DataFrame(), id="empty-result"),
            pytest.param(pd.DataFrame({"min_date": [None], "max_date": [None]}), id="null-result"),
        ],
    )
    def test_returns_none_without_snapshots(
        self,
        config: metrics_timeline.DashboardConfig,
        frame: pd.DataFrame,
    ) -> None:
        """An empty view leaves the page in its empty state."""
        with patch.object(metrics_timeline, "cached_query", return_value=frame):
            assert metrics_timeline.load_date_bounds(config) is None


@pytest.mark.parametrize("config", DASHBOARDS)
class TestLoadMetricTimeline:
    """Tests for :func:`metrics_timeline.load_metric_timeline`."""

    def test_forwards_the_date_range_and_normalises_types(self, config: metrics_timeline.DashboardConfig) -> None:
        """The query is parameterised by the inclusive date range."""
        with patch.object(metrics_timeline, "cached_query", return_value=sample_frame()) as query:
            frame = metrics_timeline.load_metric_timeline(config, dt.date(2026, 11, 1), dt.date(2026, 11, 2))

        query.assert_called_once_with(
            config.timeline_query,
            (("start_date", "2026-11-01"), ("end_date", "2026-11-02")),
        )
        assert pd.api.types.is_datetime64_any_dtype(frame["file_date"])
        assert frame["observation_count"].dtype == "int64"
        assert "measured_count" not in frame.columns

    def test_returns_the_empty_frame_unchanged(self, config: metrics_timeline.DashboardConfig) -> None:
        """The page can distinguish an empty range without extra normalisation."""
        empty = pd.DataFrame()
        with patch.object(metrics_timeline, "cached_query", return_value=empty):
            result = metrics_timeline.load_metric_timeline(config, dt.date(2026, 11, 1), dt.date(2026, 11, 2))
        assert result is empty
