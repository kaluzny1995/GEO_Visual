"""Shared engine for the GEO_Visual metrics timeline dashboards.

Each configured dashboard reads a ``geo.metrics_*_vw`` view, where GEO_ETL
unpivots one event category into one row per
``(file_date, metric_name, metric_value, metric_unit)``. Each ``file_date`` is
a daily snapshot, so aggregating by snapshot date turns every metric into its
own time series. The page renders one line chart per metric on the selected
timeline; periods where a metric has no observations are shaded and labelled
instead of breaking the shared date axis.

Avalanche ``danger_level = -1`` means "no rating". It is an encoded state in
the source feed rather than a missing measurement, so it stays in the
aggregates — that keeps off-season snapshots visible instead of leaving a gap
in the timeline. Dashboard configurations can add a note for states like this.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import error
from utils.database import DB_CONFIG, cached_query
from utils.sql import load_sql

logger = logging.getLogger(__name__)

DISTRIBUTION_QUERY_TEMPLATE = load_sql("metrics_distribution")
DISTRIBUTION_MAX_ROWS: Final = DB_CONFIG.distribution_max_rows


@dataclass(frozen=True)
class DashboardConfig:
    """Metadata and SQL scripts for one metrics timeline dashboard.

    Attributes:
        key: Short dashboard key used in filenames and test ids.
        view_name: Fully qualified ``geo`` view to read.
        page_title: Page heading and browser tab title.
        page_icon: Emoji used by Streamlit.
        description: Noun phrase used in page copy and messages, e.g.
            ``"avalanche metrics"``.
        date_bounds_query: Loaded SQL for the date picker bounds.
        timeline_query: Loaded SQL for the aggregated timeline.
        note_metric: Metric that must be present before ``note`` is shown.
        note: Optional caption explaining an encoded metric state.
        hidden_metrics: ``(metric_name, metric_unit)`` pairs to omit from the
            charts, KPIs and data table because they are too sparse to chart.
    """

    key: str
    view_name: str
    page_title: str
    page_icon: str
    description: str
    date_bounds_query: str
    timeline_query: str
    note_metric: str | None = None
    note: str | None = None
    hidden_metrics: tuple[tuple[str, str | None], ...] = ()


PALETTE: Final = ("#2dd4bf", "#fbbf24", "#60a5fa", "#fb7185", "#a78bfa", "#38bdf8")
PREDICTED_COLOR: Final = "#f472b6"
"""High-contrast pink used only for ML-predicted values and line segments."""

#: Display names for abbreviations that should not be title-cased.
METRIC_NAME_OVERRIDES: Final[dict[str, str]] = {
    "dist2land": "Distance to Land",
    "nst": "NST",
    "vei": "VEI",
    "vnum": "Volcano Number",
}


@dataclass(frozen=True)
class Aggregation:
    """One statistic that can be charted for every metric.

    Attributes:
        key: Stable identifier used by the selectbox.
        label: Human-readable statistic name.
        column: Aggregated column in the timeline SQL.
        value_format: Plotly d3 format for hover values.
        description: One-line explanation shown under the filters.
    """

    key: str
    label: str
    column: str
    value_format: str
    description: str


AGGREGATIONS: Final[dict[str, Aggregation]] = {
    "mean": Aggregation("mean", "Mean", "mean_value", ".3g", "Mean of all recorded values per snapshot"),
    "median": Aggregation("median", "Median", "median_value", ".3g", "Median of all recorded values per snapshot"),
    "max": Aggregation("max", "Maximum", "max_value", ".3g", "Highest recorded value per snapshot"),
    "sum": Aggregation("sum", "Total", "sum_value", ".3g", "Sum of all recorded values per snapshot"),
    "count": Aggregation("count", "Observations", "observation_count", ",.0f", "Rows recorded per snapshot"),
}


def load_date_bounds(config: DashboardConfig) -> tuple[dt.date, dt.date] | None:
    """Return the first and last snapshot date in the configured view.

    Args:
        config: Dashboard configuration with the date-bounds SQL.

    Returns:
        ``(min_date, max_date)``, or ``None`` when the view is empty.
    """
    frame = cached_query(config.date_bounds_query)
    if frame.empty:
        return None
    row = frame.iloc[0]
    if pd.isna(row["min_date"]) or pd.isna(row["max_date"]):
        return None
    return dt.date.fromisoformat(str(row["min_date"])), dt.date.fromisoformat(str(row["max_date"]))


def load_metric_timeline(config: DashboardConfig, start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    """Load one aggregated row per snapshot date and metric.

    Args:
        config: Dashboard configuration with the timeline SQL.
        start_date: First snapshot date to include.
        end_date: Last snapshot date to include (inclusive).

    Returns:
        A DataFrame with one row per ``(file_date, metric_name, metric_unit)``
        and the aggregates needed by every statistic in :data:`AGGREGATIONS`.
    """
    frame = cached_query(
        config.timeline_query,
        (
            ("start_date", start_date.isoformat()),
            ("end_date", end_date.isoformat()),
        ),
    )
    if frame.empty:
        return frame

    frame = frame.copy()
    frame["file_date"] = pd.to_datetime(frame["file_date"])
    frame["observation_count"] = frame["observation_count"].astype("int64")
    frame["is_predicted"] = frame["is_predicted"].fillna(False).astype(bool)
    frame = frame.sort_values(["file_date", "metric_name", "is_predicted"], ignore_index=True)
    return _drop_hidden_metrics(config, frame)


def _drop_hidden_metrics(config: DashboardConfig, frame: pd.DataFrame) -> pd.DataFrame:
    """Remove configured metric/unit pairs from the loaded timeline.

    Args:
        config: Dashboard configuration with the hidden pairs.
        frame: Timeline or raw distribution frame.

    Returns:
        The frame without the hidden metric series.
    """
    if not config.hidden_metrics or frame.empty:
        return frame
    keep = pd.Series(True, index=frame.index)
    for metric_name, metric_unit in config.hidden_metrics:
        unit = "" if metric_unit is None else metric_unit
        keep &= ~((frame["metric_name"] == metric_name) & (frame["metric_unit"].fillna("") == unit))
    return frame[keep].reset_index(drop=True)


def load_metric_distribution(config: DashboardConfig, start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    """Load raw metric values for the distribution histograms.

    Args:
        config: Dashboard configuration with the view name.
        start_date: First snapshot date to include.
        end_date: Last snapshot date to include (inclusive).

    Returns:
        A DataFrame with ``metric_name``, ``metric_unit`` and ``metric_value``
        rows for all visible metric series in the selected range.
    """
    query = DISTRIBUTION_QUERY_TEMPLATE.format(view_name=config.view_name)
    frame = cached_query(
        query,
        (
            ("start_date", start_date.isoformat()),
            ("end_date", end_date.isoformat()),
        ),
        max_rows=DISTRIBUTION_MAX_ROWS,
    )
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["metric_value"] = pd.to_numeric(frame["metric_value"], errors="coerce")
    frame["is_predicted"] = frame["is_predicted"].fillna(False).astype(bool)
    frame = frame.dropna(subset=["metric_value"]).reset_index(drop=True)
    return _drop_hidden_metrics(config, frame)


def metric_groups(frame: pd.DataFrame) -> list[tuple[str, str | None]]:
    """Return the distinct ``(metric_name, metric_unit)`` pairs in *frame*.

    Args:
        frame: Aggregated timeline frame from :func:`load_metric_timeline`.

    Returns:
        Pairs sorted by metric name, ready for one chart each.
    """
    pairs = frame[["metric_name", "metric_unit"]].drop_duplicates()
    pairs = pairs.sort_values(["metric_name", "metric_unit"])
    groups: list[tuple[str, str | None]] = []
    for metric_name, metric_unit in zip(pairs["metric_name"], pairs["metric_unit"], strict=True):
        groups.append((str(metric_name), None if pd.isna(metric_unit) else str(metric_unit)))
    return groups


def metric_label(metric_name: str, metric_unit: str | None) -> str:
    """Format a metric name and unit for a chart title.

    Args:
        metric_name: Raw view metric name, e.g. ``danger_level``.
        metric_unit: Unit paired with the metric, if any.

    Returns:
        ``Danger Level (NAPADS level)`` or just ``Danger Level``.
    """
    label = METRIC_NAME_OVERRIDES.get(metric_name, metric_name.replace("_", " ").strip().title())
    return f"{label} ({metric_unit})" if metric_unit else label


def _missing_date_runs(missing: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return contiguous ``(start, end)`` runs of missing dates.

    Args:
        missing: Boolean Series indexed by snapshot date.

    Returns:
        One pair per contiguous run of ``True`` values, in date order.
    """
    runs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    for index, is_missing in missing.items():
        timestamp = pd.Timestamp(str(index))
        if bool(is_missing):
            if start is None:
                start = timestamp
            end = timestamp
        elif start is not None and end is not None:
            runs.append((start, end))
            start = None
            end = None
    if start is not None and end is not None:
        runs.append((start, end))
    return runs


def missing_observation_runs(
    series: pd.DataFrame,
    date_index: pd.DatetimeIndex,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return the no-observation date runs for one metric.

    Args:
        series: Rows of a single metric from :func:`load_metric_timeline`.
        date_index: Full timeline shared by all charts.

    Returns:
        One ``(start, end)`` pair per contiguous run of missing snapshots.
    """
    if series.empty:
        return _missing_date_runs(pd.Series(True, index=date_index))
    plot_frame = series.set_index("file_date").reindex(date_index)
    return _missing_date_runs(plot_frame["observation_count"].isna())


def format_missing_runs(runs: list[tuple[pd.Timestamp, pd.Timestamp]]) -> str | None:
    """Format no-observation runs as a compact caption.

    Args:
        runs: Pairs returned by :func:`missing_observation_runs`.

    Returns:
        A caption such as ``No observations: 2026-10-03; 2026-10-07 to 2026-10-09.``,
        or ``None`` when there are no gaps.
    """
    if not runs:
        return None
    periods = [f"{start:%Y-%m-%d}" if start == end else f"{start:%Y-%m-%d} to {end:%Y-%m-%d}" for start, end in runs]
    return f"No observations: {'; '.join(periods)}."


def missing_value_runs(
    series: pd.DataFrame,
    date_index: pd.DatetimeIndex,
    *,
    include_predicted: bool,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return date runs with neither an observed nor a shown predicted value.

    Args:
        series: Rows of a single metric, including ``is_predicted``.
        date_index: Full timeline shared by all charts.
        include_predicted: Whether predicted dates count as covered.

    Returns:
        One ``(start, end)`` pair per contiguous uncovered run.
    """
    if series.empty:
        return _missing_date_runs(pd.Series(True, index=date_index))
    covered_dates = set(series.loc[~series["is_predicted"], "file_date"])
    if include_predicted:
        covered_dates |= set(series.loc[series["is_predicted"], "file_date"])
    covered = pd.Series([timestamp in covered_dates for timestamp in date_index], index=date_index)
    return _missing_date_runs(~covered)


def _presence_vrect_bounds(
    covered: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return shading bounds around an uncovered run using the nearest covered dates."""
    axis_start = covered.index.min() - pd.Timedelta(hours=12)
    axis_end = covered.index.max() + pd.Timedelta(hours=12)
    present = covered.index[covered]
    if present.empty:
        return axis_start, axis_end
    before = present[present < start]
    after = present[present > end]
    left = before[-1] if len(before) else axis_start
    right = after[0] if len(after) else axis_end
    return pd.Timestamp(left), pd.Timestamp(right)


def _prediction_segments(
    observed_values: pd.Series,
    predicted_values: pd.Series,
) -> list[tuple[pd.DatetimeIndex, pd.Series]]:
    """Build dashed line segments for predicted runs, anchored to nearest observations.

    Args:
        observed_values: Observed values indexed by snapshot date.
        predicted_values: Predicted values indexed by snapshot date.

    Returns:
        One ``(dates, values)`` pair per contiguous predicted run. The dates
        include the nearest observed neighbour on either side when present, so
        the dashed prediction line visibly joins the observed line.
    """
    combined = observed_values.combine_first(predicted_values)
    predicted = predicted_values.notna()
    segments: list[tuple[pd.DatetimeIndex, pd.Series]] = []
    start: int | None = None
    for position, is_predicted in enumerate(predicted.to_numpy()):
        if is_predicted and start is None:
            start = position
        elif not is_predicted and start is not None:
            end = position - 1
            left = start - 1 if start > 0 and pd.notna(combined.iloc[start - 1]) else start
            right = end + 1 if end + 1 < len(combined) and pd.notna(combined.iloc[end + 1]) else end
            dates = combined.index[left : right + 1]
            values = combined.loc[dates].dropna()
            if not values.empty:
                segments.append((pd.DatetimeIndex(values.index), values))
            start = None
    if start is not None:
        end = len(combined) - 1
        left = start - 1 if start > 0 and pd.notna(combined.iloc[start - 1]) else start
        right = end + 1 if end + 1 < len(combined) and pd.notna(combined.iloc[end + 1]) else end
        dates = combined.index[left : right + 1]
        values = combined.loc[dates].dropna()
        if not values.empty:
            segments.append((pd.DatetimeIndex(values.index), values))
    return segments


def build_metric_figure(
    series: pd.DataFrame,
    *,
    metric_name: str,
    metric_unit: str | None,
    aggregation: Aggregation,
    color: str,
    date_index: pd.DatetimeIndex | None = None,
    show_predictions: bool = True,
) -> go.Figure:
    """Build the timeline chart for one metric.

    Args:
        series: Rows of a single metric from :func:`load_metric_timeline`.
        metric_name: Raw view metric name.
        metric_unit: Unit paired with the metric, if any.
        aggregation: Statistic to plot on the y-axis.
        color: Line colour used by the metric.
        date_index: Full timeline shared by all charts. When omitted, the
            metric's own first-to-last snapshot range is used.
        show_predictions: Whether ML-predicted values should be drawn. Predicted
            values are never used for the Observations statistic.

    Returns:
        A Plotly line chart with observed and (optionally) predicted series.
        Periods with neither value are shaded; the caller lists their ranges.
    """
    series = series.sort_values(["file_date", "is_predicted"])
    observed = series[~series["is_predicted"]]
    include_predictions = show_predictions and aggregation.key != "count"
    predicted = series[series["is_predicted"]] if include_predictions else series.iloc[0:0]

    if date_index is None:
        dates = pd.concat([observed["file_date"], predicted["file_date"]]).dropna().unique()
        if len(dates):
            date_index = pd.date_range(pd.Timestamp(dates.min()), pd.Timestamp(dates.max()), freq="D")

    observed_plot = (
        observed.set_index("file_date").reindex(date_index)
        if date_index is not None
        else observed.set_index("file_date")
    )
    predicted_plot = (
        predicted.set_index("file_date").reindex(date_index)
        if date_index is not None
        else predicted.set_index("file_date")
    )
    values = observed_plot[aggregation.column]
    predicted_values = predicted_plot[aggregation.column]
    has_observed = bool(observed_plot["observation_count"].notna().any()) if not observed_plot.empty else False
    has_predicted = bool(predicted_values.notna().any())
    show_band = aggregation.key == "mean" and has_observed
    show_legend = show_band or has_predicted
    unit_suffix = f" {metric_unit}" if metric_unit and aggregation.key != "count" else ""
    covered = observed_plot["observation_count"].notna() | (
        predicted_plot["observation_count"].notna() if not predicted_plot.empty else False
    )

    figure = go.Figure()
    if show_band:
        # Draw one closed polygon per contiguous data segment. A two-trace
        # fill would create triangular artifacts across gaps in sparse series.
        valid = observed_plot["max_value"].notna() & observed_plot["min_value"].notna()
        if valid.any():
            groups = valid.ne(valid.shift(fill_value=False)).cumsum()
            for index, (_, segment) in enumerate(observed_plot[valid].groupby(groups[valid])):
                x_values = list(segment.index) + list(segment.index[::-1])
                y_values = list(segment["max_value"]) + list(segment["min_value"][::-1])
                figure.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=y_values,
                        mode="lines",
                        fill="toself",
                        line={"width": 0},
                        fillcolor=_rgba(color, 0.18),
                        name="Observed min-max",
                        showlegend=index == 0,
                        hoverinfo="skip",
                    )
                )

    if has_observed:
        figure.add_trace(
            go.Scatter(
                x=observed_plot.index,
                y=values,
                mode="lines+markers",
                name="Observed",
                line={"color": color, "width": 2.5},
                marker={"color": color, "size": 7, "line": {"color": "#0f172a", "width": 1}},
                connectgaps=False,
                showlegend=show_legend,
                hovertemplate=(
                    f"Observed<br>%{{x|%Y-%m-%d}}<br>{aggregation.label}: "
                    f"%{{y:{aggregation.value_format}}}{unit_suffix}<extra></extra>"
                ),
            )
        )

    if has_predicted:
        for segment_dates, segment_values in _prediction_segments(values, predicted_values):
            figure.add_trace(
                go.Scatter(
                    x=segment_dates,
                    y=segment_values,
                    mode="lines",
                    line={"color": PREDICTED_COLOR, "width": 2.2, "dash": "dash"},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        predicted_points = predicted_values.dropna()
        figure.add_trace(
            go.Scatter(
                x=predicted_points.index,
                y=predicted_points,
                mode="markers",
                name="Predicted (MLlib)",
                marker={
                    "color": PREDICTED_COLOR,
                    "size": 7,
                    "symbol": "diamond",
                    "line": {"color": "#0f172a", "width": 1},
                },
                hovertemplate=(
                    f"Predicted<br>%{{x|%Y-%m-%d}}<br>{aggregation.label}: "
                    f"%{{y:{aggregation.value_format}}}{unit_suffix}<extra></extra>"
                ),
            )
        )

    if date_index is not None:
        for start, end in _missing_date_runs(~covered):
            x0, x1 = _presence_vrect_bounds(covered, start, end)
            figure.add_vrect(
                x0=x0,
                x1=x1,
                fillcolor="rgba(148, 163, 184, 0.16)",
                line_width=0,
                layer="below",
            )

    if has_observed:
        first_observed = values.first_valid_index()
        last_observed = values.last_valid_index()
        if isinstance(first_observed, pd.Timestamp) and isinstance(last_observed, pd.Timestamp):
            figure.add_annotation(
                text=f"Observed {first_observed:%Y-%m-%d} to {last_observed:%Y-%m-%d}",
                xref="paper",
                yref="paper",
                x=1,
                y=1.02,
                xanchor="right",
                yanchor="bottom",
                showarrow=False,
                font={"size": 11, "color": "#94a3b8"},
            )

    y_title = aggregation.label
    if metric_unit and aggregation.key != "count":
        y_title = f"{aggregation.label} ({metric_unit})"

    x_range = None
    if date_index is not None and len(date_index):
        x_range = [
            date_index.min() - pd.Timedelta(hours=12),
            date_index.max() + pd.Timedelta(hours=12),
        ]

    figure.update_layout(
        title={
            "text": f"{metric_label(metric_name, metric_unit)} · {aggregation.label}",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.98,
            "yanchor": "top",
        },
        height=380,
        margin={"l": 72, "r": 16, "t": 80, "b": 48},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans serif", "size": 13, "color": "#e2e8f0"},
        hovermode="x unified",
        hoverlabel={"bgcolor": "#1e293b", "bordercolor": "#334155", "font": {"color": "#e2e8f0"}},
        showlegend=show_legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#e2e8f0"},
        },
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": "#94a3b8", "activecolor": "#2dd4bf"},
    )
    figure.update_xaxes(
        title_text="Snapshot date",
        tickformat="%Y-%m-%d",
        nticks=10,
        showgrid=False,
        range=x_range,
        linecolor="rgba(226, 232, 240, 0.25)",
        tickfont={"color": "#cbd5e1"},
        title_font={"color": "#e2e8f0"},
    )
    figure.update_yaxes(
        title_text=y_title,
        gridcolor="rgba(226, 232, 240, 0.14)",
        zeroline=False,
        linecolor="rgba(226, 232, 240, 0.25)",
        tickfont={"color": "#cbd5e1"},
        title_font={"color": "#e2e8f0"},
    )
    return figure


def build_distribution_figure(
    values: pd.Series,
    *,
    metric_name: str,
    metric_unit: str | None,
    color: str,
    bins: int = 20,
    predicted_values: pd.Series | None = None,
) -> go.Figure:
    """Build the value-distribution histogram for one metric.

    Args:
        values: Observed raw metric values in the selected date range.
        metric_name: Raw view metric name.
        metric_unit: Unit paired with the metric, if any.
        color: Bar colour used by the metric.
        bins: Number of equal-width histogram bins.
        predicted_values: Optional predicted values to overlay.

    Returns:
        A Plotly histogram with centred title and dark-theme styling.
    """
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    predicted = (
        pd.to_numeric(predicted_values, errors="coerce").dropna().to_numpy(dtype=float)
        if predicted_values is not None
        else np.array([], dtype=float)
    )
    combined = np.concatenate([clean, predicted]) if clean.size or predicted.size else np.array([], dtype=float)
    unit_suffix = f" {metric_unit}" if metric_unit else ""
    figure = go.Figure()
    if combined.size:
        _, boundaries = np.histogram(combined, bins=bins)
        centers = (boundaries[:-1] + boundaries[1:]) / 2
        widths = np.diff(boundaries)
        if clean.size:
            counts, _ = np.histogram(clean, bins=boundaries)
            figure.add_trace(
                go.Bar(
                    x=centers,
                    y=counts,
                    width=widths * 0.92,
                    marker={"color": _rgba(color, 0.65), "line": {"color": color, "width": 0.5}},
                    name="Observed",
                    hovertemplate=(f"Observed: %{{x:.4g}}{unit_suffix}<br>Count: %{{y:,}}<extra></extra>"),
                )
            )
        if predicted.size:
            counts, _ = np.histogram(predicted, bins=boundaries)
            figure.add_trace(
                go.Bar(
                    x=centers,
                    y=counts,
                    width=widths * 0.92,
                    marker={
                        "color": _rgba(PREDICTED_COLOR, 0.55),
                        "line": {"color": PREDICTED_COLOR, "width": 0.5},
                    },
                    name="Predicted (MLlib)",
                    hovertemplate=(f"Predicted: %{{x:.4g}}{unit_suffix}<br>Count: %{{y:,}}<extra></extra>"),
                )
            )
    else:
        figure.add_annotation(
            text="No values in this range",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#64748b"},
        )

    figure.update_layout(
        title={
            "text": "Distribution",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.98,
            "yanchor": "top",
        },
        height=380,
        margin={"l": 56, "r": 16, "t": 80, "b": 48},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans serif", "size": 13, "color": "#e2e8f0"},
        hoverlabel={"bgcolor": "#1e293b", "bordercolor": "#334155", "font": {"color": "#e2e8f0"}},
        showlegend=bool(predicted.size),
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#e2e8f0"},
        },
        bargap=0.05,
        barmode="overlay",
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": "#94a3b8", "activecolor": "#2dd4bf"},
    )
    figure.update_xaxes(
        title_text=f"Value{f' ({metric_unit})' if metric_unit else ''}",
        nticks=6,
        showgrid=False,
        linecolor="rgba(226, 232, 240, 0.25)",
        tickfont={"color": "#cbd5e1"},
        title_font={"color": "#e2e8f0"},
    )
    figure.update_yaxes(
        title_text="Count",
        gridcolor="rgba(226, 232, 240, 0.14)",
        zeroline=False,
        linecolor="rgba(226, 232, 240, 0.25)",
        tickfont={"color": "#cbd5e1"},
        title_font={"color": "#e2e8f0"},
    )
    return figure


def render_dashboard(config: DashboardConfig) -> None:
    """Render one configured metrics timeline page.

    Args:
        config: Dashboard metadata and loaded SQL scripts.
    """
    st.title(f"{config.page_icon} {config.page_title}")
    st.markdown(
        f"Daily snapshots of {config.description} from `{config.view_name}`. "
        "Each chart follows one metric across the selected snapshot dates."
    )

    try:
        bounds = load_date_bounds(config)
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load %s date bounds: %s", config.description, exc)
        st.error(f"Could not load the {config.description} view. Check the Supabase connection in the sidebar.")
        return

    if bounds is None:
        st.info(f"No {config.description} are available in the view yet.")
        return

    range_column, statistic_column, prediction_column = st.columns([2, 1, 1])
    date_range = range_column.date_input(
        "Snapshot range",
        value=bounds,
        min_value=bounds[0],
        max_value=bounds[1],
        format="YYYY-MM-DD",
    )
    aggregation_key = statistic_column.selectbox(
        "Statistic",
        options=list(AGGREGATIONS),
        format_func=lambda key: AGGREGATIONS[key].label,
        index=0,
        help=(
            "Mean, Median, Maximum and Total aggregate every recorded value. "
            "Observations counts every row in the snapshot."
        ),
    )
    show_predictions = prediction_column.checkbox(
        "Show predicted values",
        value=True,
        help=(
            "Overlay MLlib predictions for dates with no observed value. Predictions are not counted as observations."
        ),
    )

    if not isinstance(date_range, tuple) or len(date_range) != 2:
        st.info("Select both a start and an end date.")
        return
    start_date, end_date = date_range
    if start_date > end_date:
        st.warning("The start date must not be after the end date.")
        return

    try:
        frame = load_metric_timeline(config, start_date, end_date)
    except error.QueryTooLargeError:
        st.error("The selected range returns too much data. Narrow the date range.")
        return
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load the %s timeline: %s", config.description, exc)
        st.error(f"Could not load {config.description}. Check the Supabase connection in the sidebar.")
        return

    if frame.empty:
        st.info(f"No {config.description} were recorded in the selected date range.")
        return

    try:
        distribution = load_metric_distribution(config, start_date, end_date)
    except error.QueryTooLargeError:
        distribution = pd.DataFrame()
        st.warning("Distribution data is too large for the selected range; showing timelines only.")
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load the %s distribution: %s", config.description, exc)
        distribution = pd.DataFrame()
        st.warning("Distribution data could not be loaded; showing timelines only.")

    aggregation = AGGREGATIONS[aggregation_key]
    _render_summary(frame)
    coverage_note = (
        "shaded areas mark dates without observations or predictions"
        if show_predictions
        else "shaded areas mark missing observations"
    )
    st.caption(
        f"{aggregation.description} · timelines span the selected dates · "
        f"{coverage_note} · histograms show all values in the range · "
        f"source `{config.view_name}`"
    )
    if frame["is_predicted"].any():
        st.caption(
            "Predicted values are PySpark MLlib estimates for missing dates, not observations. "
            "Use **Show predicted values** to hide them."
        )
    if config.note and config.note_metric in set(frame["metric_name"]):
        st.caption(config.note)
    _render_charts(frame, distribution, aggregation, start_date, end_date, show_predictions)
    _render_data(config, frame)


def _render_summary(frame: pd.DataFrame) -> None:
    """Render snapshot, metric, observation, prediction and latest-date KPIs."""
    latest = frame["file_date"].max().date()
    observed = frame[~frame["is_predicted"]]
    predicted = frame[frame["is_predicted"]]
    columns = st.columns(5)
    columns[0].metric("Snapshots", f"{observed['file_date'].nunique():,}")
    columns[1].metric("Metrics", f"{len(metric_groups(frame)):,}")
    columns[2].metric("Observations", f"{int(observed['observation_count'].sum()):,}")
    columns[3].metric("Predicted dates", f"{predicted['file_date'].nunique():,}")
    columns[4].metric("Latest snapshot", latest.isoformat())


def _render_charts(
    frame: pd.DataFrame,
    distribution: pd.DataFrame,
    aggregation: Aggregation,
    start_date: dt.date,
    end_date: dt.date,
    show_predictions: bool,
) -> None:
    """Render a timeline and value histogram for each distinct metric."""
    date_index = pd.date_range(start_date, end_date, freq="D")
    for index, (metric_name, metric_unit) in enumerate(metric_groups(frame)):
        metric_frame = frame[
            (frame["metric_name"] == metric_name) & (frame["metric_unit"].fillna("") == (metric_unit or ""))
        ]
        color = PALETTE[index % len(PALETTE)]
        timeline_figure = build_metric_figure(
            metric_frame,
            metric_name=metric_name,
            metric_unit=metric_unit,
            aggregation=aggregation,
            color=color,
            date_index=date_index,
            show_predictions=show_predictions,
        )
        distribution_frame = distribution[
            (distribution["metric_name"] == metric_name)
            & (distribution["metric_unit"].fillna("") == (metric_unit or ""))
        ]
        observed_values = (
            distribution_frame.loc[~distribution_frame["is_predicted"], "metric_value"]
            if not distribution_frame.empty
            else pd.Series(dtype="float64")
        )
        predicted_values = (
            distribution_frame.loc[distribution_frame["is_predicted"], "metric_value"]
            if show_predictions and not distribution_frame.empty
            else pd.Series(dtype="float64")
        )
        distribution_figure = build_distribution_figure(
            observed_values,
            metric_name=metric_name,
            metric_unit=metric_unit,
            color=color,
            predicted_values=predicted_values,
        )

        timeline_column, distribution_column = st.columns([2, 1])
        with timeline_column:
            st.plotly_chart(timeline_figure, width="stretch", key=f"metric-timeline-{index}")
            missing_caption = format_missing_runs(
                missing_value_runs(metric_frame, date_index, include_predicted=show_predictions)
            )
            if missing_caption:
                st.caption(missing_caption)
        with distribution_column:
            st.plotly_chart(
                distribution_figure,
                width="stretch",
                config={"displayModeBar": False},
                key=f"metric-distribution-{index}",
            )


def _render_data(config: DashboardConfig, frame: pd.DataFrame) -> None:
    """Render the aggregated rows and a CSV download behind an expander."""
    with st.expander("Aggregated data"):
        display = frame.copy()
        display["file_date"] = display["file_date"].dt.date
        display["is_predicted"] = display["is_predicted"].map({True: "Predicted", False: "Observed"})
        display = display.rename(columns={"is_predicted": "series"})
        st.dataframe(display, hide_index=True)
        st.download_button(
            "Download CSV",
            data=display.to_csv(index=False),
            file_name=f"{config.key}_metrics_timeline.csv",
            mime="text/csv",
        )


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert a ``#rrggbb`` colour to a Plotly ``rgba()`` string."""
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha})"
