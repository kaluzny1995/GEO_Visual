"""Tests for the shared metrics timeline engine and Plotly figures."""

import pandas as pd
import pytest

from dashboard import metrics_timeline as timeline


def sample_frame() -> pd.DataFrame:
    """Two daily snapshots for one metric, already aggregated by SQL."""
    return pd.DataFrame(
        {
            "file_date": pd.to_datetime(["2026-11-01", "2026-11-02"]),
            "metric_name": ["danger_level", "danger_level"],
            "metric_unit": ["NAPADS level", "NAPADS level"],
            "observation_count": [10, 12],
            "mean_value": [1.5, 2.0],
            "median_value": [1.5, 1.75],
            "max_value": [3.0, 4.0],
            "min_value": [1.0, 1.5],
            "sum_value": [6.0, 12.0],
        }
    )


class TestMetricGroups:
    """Tests for :func:`metric_groups`."""

    def test_returns_sorted_name_and_unit_pairs(self) -> None:
        """Every distinct metric gets exactly one pair for its chart."""
        frame = pd.concat(
            [
                sample_frame(),
                sample_frame().assign(metric_name="size", metric_unit="destructive size class"),
            ],
            ignore_index=True,
        )
        assert timeline.metric_groups(frame) == [
            ("danger_level", "NAPADS level"),
            ("size", "destructive size class"),
        ]


@pytest.mark.parametrize(
    "metric_name, metric_unit, expected",
    [
        pytest.param("danger_level", "NAPADS level", "Danger Level (NAPADS level)", id="with-unit"),
        pytest.param("size", None, "Size", id="without-unit"),
        pytest.param("area", "km²", "Area (km²)", id="drought-area"),
    ],
)
def test_metric_label(metric_name: str, metric_unit: str | None, expected: str) -> None:
    """Metric names are humanised and the unit is appended when present."""
    assert timeline.metric_label(metric_name, metric_unit) == expected


class TestBuildMetricFigure:
    """Tests for :func:`build_metric_figure`."""

    @pytest.mark.parametrize(
        "key, column, expected_values, has_band, expected_y_title",
        [
            pytest.param("mean", "mean_value", [1.5, 2.0], True, "Mean (NAPADS level)", id="mean"),
            pytest.param("median", "median_value", [1.5, 1.75], False, "Median (NAPADS level)", id="median"),
            pytest.param("max", "max_value", [3.0, 4.0], False, "Maximum (NAPADS level)", id="maximum"),
            pytest.param("sum", "sum_value", [6.0, 12.0], False, "Total (NAPADS level)", id="total"),
            pytest.param("count", "observation_count", [10, 12], False, "Observations", id="observations"),
        ],
    )
    def test_figure_uses_the_selected_aggregation(
        self,
        key: str,
        column: str,
        expected_values: list[float],
        has_band: bool,
        expected_y_title: str,
    ) -> None:
        """Every dropdown statistic maps to its own SQL column and y-axis."""
        aggregation = timeline.AGGREGATIONS[key]
        figure = timeline.build_metric_figure(
            sample_frame(),
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=aggregation,
            color="#2dd4bf",
        )

        assert aggregation.column == column
        assert len(figure.data) == (3 if has_band else 1)
        assert list(figure.data[-1].y) == expected_values
        assert figure.layout.yaxis.title.text == expected_y_title
        assert figure.layout.showlegend is has_band
        if has_band:
            assert figure.data[1].fill == "tonexty"
            assert figure.data[-1].mode == "lines+markers"
            assert figure.data[-1].name == "Mean"
            assert figure.layout.title.text == "Danger Level (NAPADS level) · Mean"
            assert figure.layout.font.color == "#e2e8f0"

    def test_figure_notes_the_observed_range(self) -> None:
        """The chart labels the metric's own first-to-last observation."""
        figure = timeline.build_metric_figure(
            sample_frame(),
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
        )

        assert any("Observed 2026-11-01 to 2026-11-02" in annotation.text for annotation in figure.layout.annotations)

    def test_shared_date_index_keeps_the_full_timeline_and_marks_gaps(self) -> None:
        """A metric that starts later stays on the full axis and its gap is labelled."""
        figure = timeline.build_metric_figure(
            sample_frame(),
            metric_name="size",
            metric_unit="destructive size class",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=pd.date_range("2026-09-01", "2026-11-02", freq="D"),
        )

        line = figure.data[-1]
        assert len(line.x) == 63
        assert pd.isna(line.y[0])
        assert len(figure.layout.shapes) == 1
        assert figure.layout.shapes[0].fillcolor == "rgba(148, 163, 184, 0.16)"
        assert any("No size observations" in annotation.text for annotation in figure.layout.annotations)
        assert any("2026-09-01 to 2026-10-31" in annotation.text for annotation in figure.layout.annotations)

    def test_full_metric_has_no_missing_shading(self) -> None:
        """A metric present on every snapshot needs no no-data marker."""
        figure = timeline.build_metric_figure(
            sample_frame(),
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=pd.date_range("2026-11-01", "2026-11-02", freq="D"),
        )

        assert not figure.layout.shapes
        assert not any("observations" in annotation.text for annotation in figure.layout.annotations)

    def test_no_rating_values_stay_on_the_timeline(self) -> None:
        """``danger_level = -1`` is plotted instead of leaving the early months blank."""
        frame = sample_frame()
        frame.loc[0, ["mean_value", "max_value", "min_value", "sum_value"]] = [-1.0, -1.0, -1.0, -10.0]
        figure = timeline.build_metric_figure(
            frame,
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
        )

        assert list(figure.data[-1].y) == [-1.0, 2.0]

    def test_missing_days_break_the_line(self) -> None:
        """A day without a snapshot becomes a gap, not a straight interpolation."""
        frame = sample_frame()
        frame.loc[1, "file_date"] = pd.Timestamp("2026-11-04")
        figure = timeline.build_metric_figure(
            frame,
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
        )

        y_values = list(figure.data[-1].y)
        assert len(y_values) == 4
        assert pd.isna(y_values[2])
        assert len(figure.layout.shapes) == 1
        assert any("No danger level observations" in annotation.text for annotation in figure.layout.annotations)

    def test_metric_without_any_data_marks_the_whole_timeline(self) -> None:
        """A metric with no observations gets a full-width no-data marker."""
        empty = sample_frame().iloc[0:0]
        figure = timeline.build_metric_figure(
            empty,
            metric_name="size",
            metric_unit="destructive size class",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=pd.date_range("2026-09-01", "2026-09-03", freq="D"),
        )

        assert not figure.data
        assert len(figure.layout.shapes) == 1
        assert any("No size observations" in annotation.text for annotation in figure.layout.annotations)
        assert any("2026-09-01 to 2026-09-03" in annotation.text for annotation in figure.layout.annotations)


@pytest.mark.parametrize(
    "color, alpha, expected",
    [
        pytest.param("#2dd4bf", 0.18, "rgba(45, 212, 191, 0.18)", id="teal"),
        pytest.param("#fbbf24", 0.5, "rgba(251, 191, 36, 0.5)", id="amber"),
    ],
)
def test_rgba_converts_hex_colours(color: str, alpha: float, expected: str) -> None:
    """The band fill uses the metric colour with a fixed transparency."""
    assert timeline._rgba(color, alpha) == expected
