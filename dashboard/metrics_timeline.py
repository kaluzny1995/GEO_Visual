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

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import error
from utils.database import cached_query

logger = logging.getLogger(__name__)


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
    frame = frame.sort_values(["file_date", "metric_name"], ignore_index=True)
    return _drop_hidden_metrics(config, frame)


def _drop_hidden_metrics(config: DashboardConfig, frame: pd.DataFrame) -> pd.DataFrame:
    """Remove configured metric/unit pairs from the loaded timeline.

    Args:
        config: Dashboard configuration with the hidden pairs.
        frame: Aggregated timeline frame.

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
    label = metric_name.replace("_", " ").strip().title()
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


def build_metric_figure(
    series: pd.DataFrame,
    *,
    metric_name: str,
    metric_unit: str | None,
    aggregation: Aggregation,
    color: str,
    date_index: pd.DatetimeIndex | None = None,
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

    Returns:
        A Plotly line chart with one marker per snapshot date. Periods where
        the metric has no observations are shaded and labelled.
    """
    plot_frame = series.sort_values("file_date").set_index("file_date")
    if date_index is None and not plot_frame.empty:
        date_index = pd.date_range(plot_frame.index.min(), plot_frame.index.max(), freq="D")
    if date_index is not None:
        plot_frame = plot_frame.reindex(date_index)

    values = plot_frame[aggregation.column]
    has_data = bool(plot_frame["observation_count"].notna().any())
    show_band = aggregation.key == "mean" and has_data
    unit_suffix = f" {metric_unit}" if metric_unit and aggregation.key != "count" else ""

    figure = go.Figure()
    if show_band:
        # A translucent band keeps the spread across forecast zones visible
        # without adding a second chart for every metric.
        figure.add_trace(
            go.Scatter(
                x=plot_frame.index,
                y=plot_frame["max_value"],
                mode="lines",
                line={"width": 0},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=plot_frame.index,
                y=plot_frame["min_value"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor=_rgba(color, 0.18),
                name="Observed min-max",
                hoverinfo="skip",
            )
        )

    if has_data:
        figure.add_trace(
            go.Scatter(
                x=plot_frame.index,
                y=values,
                mode="lines+markers",
                name=aggregation.label,
                line={"color": color, "width": 2.5},
                marker={"color": color, "size": 7, "line": {"color": "#0f172a", "width": 1}},
                connectgaps=False,
                showlegend=show_band,
                hovertemplate=(
                    f"%{{x|%Y-%m-%d}}<br>{aggregation.label}: "
                    f"%{{y:{aggregation.value_format}}}{unit_suffix}<extra></extra>"
                ),
            )
        )

    missing = plot_frame["observation_count"].isna()
    for start, end in _missing_date_runs(missing):
        period = f"{start:%Y-%m-%d}" if start == end else f"{start:%Y-%m-%d} to {end:%Y-%m-%d}"
        run_end = end + pd.Timedelta(days=1)
        unit_suffix = f" ({metric_unit})" if metric_unit else ""
        figure.add_vrect(
            x0=start,
            x1=run_end,
            fillcolor="rgba(148, 163, 184, 0.16)",
            line_width=0,
            layer="below",
        )
        figure.add_annotation(
            text=f"No {metric_name.replace('_', ' ')}{unit_suffix} observations<br>{period}",
            x=start + (run_end - start) / 2,
            y=0.5,
            xref="x",
            yref="paper",
            showarrow=False,
            font={"size": 11, "color": "#cbd5e1"},
            bgcolor="rgba(15, 23, 42, 0.90)",
        )

    if has_data:
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
    if not plot_frame.empty:
        x_range = [
            plot_frame.index.min() - pd.Timedelta(hours=12),
            plot_frame.index.max() + pd.Timedelta(hours=12),
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
        showlegend=show_band,
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

    range_column, statistic_column = st.columns([2, 1])
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

    aggregation = AGGREGATIONS[aggregation_key]
    _render_summary(frame)
    st.caption(
        f"{aggregation.description} · each chart spans the selected dates · "
        f"shaded areas mark missing observations · source `{config.view_name}`"
    )
    if config.note and config.note_metric in set(frame["metric_name"]):
        st.caption(config.note)
    _render_charts(frame, aggregation, start_date, end_date)
    _render_data(config, frame)


def _render_summary(frame: pd.DataFrame) -> None:
    """Render the snapshot, metric, observation and latest-date KPIs."""
    latest = frame["file_date"].max().date()
    columns = st.columns(4)
    columns[0].metric("Snapshots", f"{frame['file_date'].nunique():,}")
    columns[1].metric("Metrics", f"{len(metric_groups(frame)):,}")
    columns[2].metric("Observations", f"{int(frame['observation_count'].sum()):,}")
    columns[3].metric("Latest snapshot", latest.isoformat())


def _render_charts(
    frame: pd.DataFrame,
    aggregation: Aggregation,
    start_date: dt.date,
    end_date: dt.date,
) -> None:
    """Render one full-width line chart per distinct metric on the shared timeline."""
    date_index = pd.date_range(start_date, end_date, freq="D")
    for index, (metric_name, metric_unit) in enumerate(metric_groups(frame)):
        metric_frame = frame[
            (frame["metric_name"] == metric_name) & (frame["metric_unit"].fillna("") == (metric_unit or ""))
        ]
        figure = build_metric_figure(
            metric_frame,
            metric_name=metric_name,
            metric_unit=metric_unit,
            aggregation=aggregation,
            color=PALETTE[index % len(PALETTE)],
            date_index=date_index,
        )
        st.plotly_chart(figure, width="stretch", key=f"metric-{index}")


def _render_data(config: DashboardConfig, frame: pd.DataFrame) -> None:
    """Render the aggregated rows and a CSV download behind an expander."""
    with st.expander("Aggregated data"):
        display = frame.copy()
        display["file_date"] = display["file_date"].dt.date
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
