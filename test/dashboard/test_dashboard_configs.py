"""Tests for the natural-phenomenon dashboard configurations."""

import datetime as dt
from unittest.mock import patch

import pandas as pd
import pytest

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

DASHBOARDS = [
    pytest.param(avalanche_timeline.DASHBOARD, id="avalanche"),
    pytest.param(drought_timeline.DASHBOARD, id="drought"),
    pytest.param(earthquake_timeline.DASHBOARD, id="earthquake"),
    pytest.param(fire_timeline.DASHBOARD, id="fire"),
    pytest.param(flood_timeline.DASHBOARD, id="flood"),
    pytest.param(iceberg_timeline.DASHBOARD, id="iceberg"),
    pytest.param(storm_timeline.DASHBOARD, id="storm"),
    pytest.param(volcano_timeline.DASHBOARD, id="volcano"),
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


@pytest.mark.parametrize(
    "config, expected",
    [
        pytest.param(avalanche_timeline.DASHBOARD, (), id="avalanche"),
        pytest.param(drought_timeline.DASHBOARD, (), id="drought"),
        pytest.param(earthquake_timeline.DASHBOARD, (("magnitude", "mlr"),), id="earthquake"),
        pytest.param(fire_timeline.DASHBOARD, (("geometry_count", None),), id="fire"),
        pytest.param(flood_timeline.DASHBOARD, (("baseline_days", None), ("magnitude", None)), id="flood"),
        pytest.param(iceberg_timeline.DASHBOARD, (), id="iceberg"),
        pytest.param(storm_timeline.DASHBOARD, (), id="storm"),
        pytest.param(
            volcano_timeline.DASHBOARD,
            (("casualties", "people"), ("damage", "million USD"), ("magnitude", None)),
            id="volcano",
        ),
    ],
)
def test_hidden_metric_configuration(
    config: metrics_timeline.DashboardConfig,
    expected: tuple[tuple[str, str | None], ...],
) -> None:
    """Sparse or flat metric series are explicitly hidden per dashboard."""
    assert config.hidden_metrics == expected


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


@pytest.mark.parametrize("config", DASHBOARDS)
class TestLoadMetricDistribution:
    """Tests for :func:`metrics_timeline.load_metric_distribution`."""

    def test_forwards_the_range_and_bins_raw_values(self, config: metrics_timeline.DashboardConfig) -> None:
        """The distribution query is parametrized by the date range."""
        raw = pd.DataFrame(
            {
                "metric_name": ["area", "area", "area"],
                "metric_unit": ["km²", "km²", "km²"],
                "metric_value": [1.0, 2.0, 3.0],
            }
        )
        query = metrics_timeline.DISTRIBUTION_QUERY_TEMPLATE.format(view_name=config.view_name)
        with patch.object(metrics_timeline, "cached_query", return_value=raw) as cached:
            frame = metrics_timeline.load_metric_distribution(config, dt.date(2026, 11, 1), dt.date(2026, 11, 2))

        cached.assert_called_once_with(
            query,
            (("start_date", "2026-11-01"), ("end_date", "2026-11-02")),
            max_rows=metrics_timeline.DISTRIBUTION_MAX_ROWS,
        )
        assert frame["metric_value"].tolist() == [1.0, 2.0, 3.0]


def test_load_metric_timeline_filters_hidden_series() -> None:
    """The fire timeline omits the configured geometry-count series."""
    frame = pd.concat(
        [
            sample_frame(),
            sample_frame().assign(metric_name="geometry_count", metric_unit=None),
        ],
        ignore_index=True,
    )
    with patch.object(metrics_timeline, "cached_query", return_value=frame):
        result = metrics_timeline.load_metric_timeline(
            fire_timeline.DASHBOARD,
            dt.date(2026, 11, 1),
            dt.date(2026, 11, 2),
        )

    assert metrics_timeline.metric_groups(result) == [("area", "km²")]


def test_filters_hidden_metric_series() -> None:
    """The earthquake distribution omits the hidden mlr magnitude scale."""
    raw = pd.DataFrame(
        {
            "metric_name": ["magnitude", "magnitude", "depth"],
            "metric_unit": ["Mw", "mlr", "km"],
            "metric_value": [4.5, 3.2, 10.0],
        }
    )
    with patch.object(metrics_timeline, "cached_query", return_value=raw):
        frame = metrics_timeline.load_metric_distribution(
            earthquake_timeline.DASHBOARD,
            dt.date(2026, 11, 1),
            dt.date(2026, 11, 2),
        )

    assert set(frame["metric_unit"]) == {"Mw", "km"}
