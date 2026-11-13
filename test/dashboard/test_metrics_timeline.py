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
            "is_predicted": [False, False],
            "observation_count": [10, 12],
            "mean_value": [1.5, 2.0],
            "median_value": [1.5, 1.75],
            "max_value": [3.0, 4.0],
            "min_value": [1.0, 1.5],
            "sum_value": [6.0, 12.0],
        }
    )


def predicted_frame() -> pd.DataFrame:
    """Two observed snapshots plus two predicted gap snapshots for one metric."""
    observed = sample_frame()
    predicted = observed.iloc[[0, 1]].assign(
        file_date=pd.to_datetime(["2026-11-03", "2026-11-04"]),
        is_predicted=True,
        observation_count=1,
        mean_value=[2.5, 3.0],
        median_value=[2.5, 3.0],
        max_value=[2.5, 3.0],
        min_value=[2.5, 3.0],
        sum_value=[2.5, 3.0],
    )
    return pd.concat([observed, predicted], ignore_index=True)


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
        pytest.param("area", "km²", "Area (km²)", id="fire-and-drought-area"),
        pytest.param("percent_contained", "%", "Percent Contained (%)", id="fire-percent-contained"),
        pytest.param("magnitude", "Mw", "Magnitude (Mw)", id="earthquake-magnitude"),
        pytest.param("nst", "stations", "NST (stations)", id="earthquake-stations"),
        pytest.param("wind speed", "km/h", "Wind Speed (km/h)", id="storm-wind-speed"),
        pytest.param("surface", "N/m²", "Surface (N/m²)", id="iceberg-surface"),
        pytest.param("dist2land", "km", "Distance to Land (km)", id="storm-dist2land"),
        pytest.param("vei", "VEI", "VEI (VEI)", id="volcano-vei"),
        pytest.param("vnum", "Smithsonian GVP", "Volcano Number (Smithsonian GVP)", id="volcano-vnum"),
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
        assert len(figure.data) == (2 if has_band else 1)
        assert list(figure.data[-1].y) == expected_values
        assert figure.layout.yaxis.title.text == expected_y_title
        assert figure.layout.showlegend is has_band
        assert figure.layout.title.x == 0.5
        assert figure.layout.title.xanchor == "center"
        assert figure.layout.title.y == 0.98
        assert figure.layout.margin.t == 80
        if has_band:
            band = figure.data[0]
            assert band.fill == "toself"
            assert band.name == "Observed min-max"
            assert len(band.x) == 4
            assert figure.data[-1].mode == "lines+markers"
            assert figure.data[-1].name == "Observed"
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
        """A metric that starts later stays on the full axis and its gap is shaded."""
        series = sample_frame()
        date_index = pd.date_range("2026-09-01", "2026-11-02", freq="D")
        figure = timeline.build_metric_figure(
            series,
            metric_name="size",
            metric_unit="destructive size class",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=date_index,
        )

        line = figure.data[-1]
        assert len(line.x) == 63
        assert pd.isna(line.y[0])
        assert len(figure.layout.shapes) == 1
        assert figure.layout.shapes[0].fillcolor == "rgba(148, 163, 184, 0.16)"
        assert timeline.format_missing_runs(timeline.missing_observation_runs(series, date_index)) == (
            "No observations: 2026-09-01 to 2026-10-31."
        )

    def test_sparse_metric_band_is_split_into_closed_polygons(self) -> None:
        """The min-max band never bridges a no-data gap with a triangular fill."""
        frame = pd.concat(
            [
                sample_frame(),
                sample_frame().assign(file_date=pd.to_datetime(["2026-11-05", "2026-11-06"])),
            ],
            ignore_index=True,
        )
        figure = timeline.build_metric_figure(
            frame,
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=pd.date_range("2026-11-01", "2026-11-06", freq="D"),
        )

        band_traces = [trace for trace in figure.data if trace.fill == "toself"]
        assert len(band_traces) == 2
        assert all(len(trace.x) == 4 for trace in band_traces)
        assert not any(trace.fill == "tonexty" for trace in figure.data)

    @pytest.mark.parametrize(
        "dates, index_bounds, expected_x0, expected_x1",
        [
            pytest.param(
                ["2026-11-01", "2026-11-04"],
                ("2026-11-01", "2026-11-04"),
                "2026-11-01",
                "2026-11-04",
                id="internal-gap",
            ),
            pytest.param(
                ["2026-11-01", "2026-11-02"],
                ("2026-10-30", "2026-11-02"),
                "2026-10-29 12:00",
                "2026-11-01",
                id="leading-gap",
            ),
            pytest.param(
                ["2026-11-01", "2026-11-02"],
                ("2026-11-01", "2026-11-04"),
                "2026-11-02",
                "2026-11-04 12:00",
                id="trailing-gap",
            ),
        ],
    )
    def test_gap_shading_touches_nearest_data_points(
        self,
        dates: list[str],
        index_bounds: tuple[str, str],
        expected_x0: str,
        expected_x1: str,
    ) -> None:
        """The grey field reaches the adjacent markers instead of leaving blank slivers."""
        frame = sample_frame().assign(file_date=pd.to_datetime(dates))
        figure = timeline.build_metric_figure(
            frame,
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=pd.date_range(*index_bounds, freq="D"),
        )

        shape = figure.layout.shapes[0]
        assert pd.Timestamp(shape.x0) == pd.Timestamp(expected_x0)
        assert pd.Timestamp(shape.x1) == pd.Timestamp(expected_x1)

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

    def test_predicted_values_get_a_distinct_dashed_series_and_legend(self) -> None:
        """Predicted rows are drawn with the amber-pink dashed style and a legend."""
        figure = timeline.build_metric_figure(
            predicted_frame(),
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=pd.date_range("2026-11-01", "2026-11-04", freq="D"),
        )

        names = [trace.name for trace in figure.data]
        assert "Observed" in names
        assert "Predicted (MLlib)" in names
        predicted_markers = next(trace for trace in figure.data if trace.name == "Predicted (MLlib)")
        assert list(predicted_markers.x) == list(pd.to_datetime(["2026-11-03", "2026-11-04"]))
        dashed = [trace for trace in figure.data if getattr(trace.line, "dash", None) == "dash"]
        assert dashed
        assert all(trace.line.color == timeline.PREDICTED_COLOR for trace in dashed)
        assert figure.layout.showlegend is True

    def test_hiding_predictions_removes_their_traces(self) -> None:
        """The show-predictions toggle removes predicted markers and dashed lines."""
        figure = timeline.build_metric_figure(
            predicted_frame(),
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=pd.date_range("2026-11-01", "2026-11-04", freq="D"),
            show_predictions=False,
        )

        assert "Predicted (MLlib)" not in [trace.name for trace in figure.data]
        assert not any(getattr(trace.line, "dash", None) == "dash" for trace in figure.data)

    def test_predicted_dates_cover_missing_shading(self) -> None:
        """Dates covered by predictions are not shaded as missing."""
        frame = predicted_frame()
        date_index = pd.date_range("2026-11-01", "2026-11-04", freq="D")

        assert timeline.missing_value_runs(frame, date_index, include_predicted=True) == []
        assert timeline.missing_value_runs(frame, date_index, include_predicted=False) == [
            (pd.Timestamp("2026-11-03"), pd.Timestamp("2026-11-04"))
        ]

    def test_observations_statistic_never_includes_predictions(self) -> None:
        """Predicted rows cannot inflate the Observations statistic."""
        figure = timeline.build_metric_figure(
            predicted_frame(),
            metric_name="danger_level",
            metric_unit="NAPADS level",
            aggregation=timeline.AGGREGATIONS["count"],
            color="#2dd4bf",
            date_index=pd.date_range("2026-11-01", "2026-11-04", freq="D"),
            show_predictions=True,
        )

        assert "Predicted (MLlib)" not in [trace.name for trace in figure.data]

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
        assert timeline.missing_observation_runs(frame, pd.date_range("2026-11-01", "2026-11-04", freq="D")) == [
            (pd.Timestamp("2026-11-02"), pd.Timestamp("2026-11-03"))
        ]

    def test_metric_without_any_data_marks_the_whole_timeline(self) -> None:
        """A metric with no observations gets a full-width no-data marker."""
        empty = sample_frame().iloc[0:0]
        date_index = pd.date_range("2026-09-01", "2026-09-03", freq="D")
        figure = timeline.build_metric_figure(
            empty,
            metric_name="size",
            metric_unit="destructive size class",
            aggregation=timeline.AGGREGATIONS["mean"],
            color="#2dd4bf",
            date_index=date_index,
        )

        assert not figure.data
        assert len(figure.layout.shapes) == 1
        assert timeline.format_missing_runs(timeline.missing_observation_runs(empty, date_index)) == (
            "No observations: 2026-09-01 to 2026-09-03."
        )


def test_distribution_figure_has_value_bars() -> None:
    """The histogram bins raw values and uses the metric colour."""
    figure = timeline.build_distribution_figure(
        pd.Series([1.0, 2.0, 2.0, 3.0]),
        metric_name="area",
        metric_unit="km²",
        color="#2dd4bf",
    )

    assert len(figure.data) == 1
    assert sum(figure.data[0].y) == 4
    assert figure.data[0].marker.color == "rgba(45, 212, 191, 0.65)"
    assert figure.layout.title.text == "Distribution"
    assert figure.layout.xaxis.title.text == "Value (km²)"
    assert figure.layout.title.x == 0.5
    assert figure.layout.yaxis.title.text == "Count"


def test_distribution_figure_overlays_predicted_values() -> None:
    """Predicted values get their own histogram series and legend entry."""
    figure = timeline.build_distribution_figure(
        pd.Series([1.0, 2.0, 3.0]),
        predicted_values=pd.Series([4.0, 5.0]),
        metric_name="area",
        metric_unit="km²",
        color="#2dd4bf",
    )

    names = [trace.name for trace in figure.data]
    assert names == ["Observed", "Predicted (MLlib)"]
    assert sum(figure.data[0].y) == 3
    assert sum(figure.data[1].y) == 2
    assert figure.layout.showlegend is True
    assert figure.data[1].marker.line.color == timeline.PREDICTED_COLOR


def test_distribution_figure_handles_an_empty_range() -> None:
    """An empty range gets an explanatory placeholder instead of a bar trace."""
    figure = timeline.build_distribution_figure(
        pd.Series(dtype="float64"),
        metric_name="area",
        metric_unit="km²",
        color="#2dd4bf",
    )

    assert not figure.data
    assert any("No values in this range" in annotation.text for annotation in figure.layout.annotations)


def test_format_missing_runs_lists_multiple_ranges() -> None:
    """The caption squeezes several no-data ranges into one readable line."""
    runs = [
        (pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-01")),
        (pd.Timestamp("2026-11-03"), pd.Timestamp("2026-11-04")),
    ]

    assert timeline.format_missing_runs(runs) == "No observations: 2026-11-01; 2026-11-03 to 2026-11-04."
    assert timeline.format_missing_runs([]) is None


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
