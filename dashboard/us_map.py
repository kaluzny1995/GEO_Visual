"""United States phenomenon map dashboard."""

import datetime as dt
import html
import logging
from dataclasses import dataclass
from typing import Final

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import error
from utils.database import cached_query
from utils.sql import load_sql

logger = logging.getLogger(__name__)

PAGE_TITLE = "United States phenomenon map"
PAGE_ICON = "🇺🇸"
DEFAULT_MIN_MAGNITUDE: Final = 2.5
MAP_MAX_ROWS: Final = 50_000
MAP_QUERY = load_sql("phenomenons_us_map")
MAP_DATE_BOUNDS_QUERY = load_sql("phenomenons_us_map_date_bounds")

MAP_STYLES: Final = """
<style>
.us-map-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr));
    gap: 0.6rem;
    margin: 0.25rem 0 0.75rem;
}
.us-map-card {
    border: 1px solid #334155;
    border-radius: 0.75rem;
    background: rgba(30, 41, 59, 0.55);
    padding: 0.7rem 0.8rem;
    min-width: 0;
}
.us-map-card-header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.us-map-card-emoji {
    font-size: 1.25rem;
    line-height: 1;
}
.us-map-card-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: #e2e8f0;
}
.us-map-card-count {
    margin-top: 0.35rem;
    font-size: 1.9rem;
    line-height: 1.05;
    font-weight: 700;
    color: #f8fafc;
}
.us-map-card-label {
    font-size: 0.66rem;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #94a3b8;
}
.us-map-card-detail {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin-top: 0.35rem;
    font-size: 0.74rem;
    color: #94a3b8;
}
.us-map-card-detail strong {
    font-size: 0.78rem;
    font-weight: 600;
    color: #cbd5e1;
    text-align: right;
}
.us-map-size-legend {
    border: 1px solid #334155;
    border-radius: 0.75rem;
    background: rgba(30, 41, 59, 0.55);
    padding: 0.7rem 0.9rem;
    margin: 0.25rem 0 0.75rem;
}
.us-map-size-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 0.5rem;
}
.us-map-size-title span {
    font-size: 0.78rem;
    font-weight: 400;
    color: #94a3b8;
}
.us-map-size-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
    align-items: flex-end;
}
.us-map-size-item {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 9rem;
}
.us-map-size-name {
    font-size: 0.78rem;
    font-weight: 600;
    color: #cbd5e1;
}
.us-map-size-range {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
}
.us-map-size-emoji {
    line-height: 1;
}
.us-map-size-value {
    font-size: 0.82rem;
    color: #e2e8f0;
}
.us-map-size-arrow {
    font-size: 0.75rem;
    color: #94a3b8;
}
.us-map-size-unit {
    font-size: 0.7rem;
    color: #94a3b8;
}
</style>
"""


@dataclass(frozen=True)
class PhenomenonStyle:
    """Display and map style for one phenomenon.

    Attributes:
        emoji: Emoji shown in the legend, hover text, selector and map.
        metric_name: Main metric used for marker size.
        metric_unit: Unit of the main metric.
        min_size: Emoji font size for the lowest observed main metric value.
        max_size: Emoji font size for the highest observed main metric value.
    """

    emoji: str
    metric_name: str
    metric_unit: str
    min_size: int
    max_size: int


PHENOMENON_ORDER: Final = (
    "Avalanche",
    "Drought",
    "Earthquake",
    "Fire",
    "Flood",
    "Storm",
    "Volcano",
)

PHENOMENA: Final[dict[str, PhenomenonStyle]] = {
    "Avalanche": PhenomenonStyle("❄️", "size", "destructive size class", 10, 20),
    "Drought": PhenomenonStyle("🌵", "area", "km²", 12, 22),
    "Earthquake": PhenomenonStyle("🏚️", "magnitude", "Mw", 6, 14),
    "Fire": PhenomenonStyle("🔥", "area", "km²", 9, 18),
    "Flood": PhenomenonStyle("🌊", "discharge", "m³/s", 10, 21),
    "Storm": PhenomenonStyle("⛈️", "wind speed", "km/h", 11, 21),
    "Volcano": PhenomenonStyle("🌋", "vei", "VEI", 12, 24),
}


def load_map_date_bounds() -> tuple[dt.date, dt.date] | None:
    """Return the first and last event start date for the map date picker.

    Returns:
        ``(min_date, max_date)``, or ``None`` when the view has no dated POIs.
    """
    frame = cached_query(MAP_DATE_BOUNDS_QUERY)
    if frame.empty:
        return None
    row = frame.iloc[0]
    if pd.isna(row["min_date"]) or pd.isna(row["max_date"]):
        return None
    return dt.date.fromisoformat(str(row["min_date"])), dt.date.fromisoformat(str(row["max_date"]))


def load_map_data(min_magnitude: float, start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    """Load one POI per natural-phenomenon event.

    Args:
        min_magnitude: Minimum earthquake magnitude to include.
        start_date: First event start date to include.
        end_date: Last event start date to include (inclusive).

    Returns:
        A DataFrame with location, metric, event and hover fields.
    """
    frame = cached_query(
        MAP_QUERY,
        (
            ("min_magnitude", min_magnitude),
            ("start_date", start_date.isoformat()),
            ("end_date", end_date.isoformat()),
        ),
        max_rows=MAP_MAX_ROWS,
    )
    if frame.empty:
        return frame

    frame = frame.copy()
    for column in ("latitude", "longitude", "metric_value"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    for column in ("event_start_date", "event_end_date"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")

    frame["intensity"] = _normalise_intensity(frame)
    frame["text_size"] = _text_sizes(frame)
    frame["hover_text"] = [_hover_text(row) for row in frame.itertuples(index=False)]
    return frame


def _normalise_intensity(frame: pd.DataFrame) -> pd.Series:
    """Normalise each phenomenon's main metric to the 0-1 size range.

    Args:
        frame: Map data with ``event_category`` and ``metric_value``.

    Returns:
        A float Series where 0 is the lowest observed value and 1 the highest
        within the same phenomenon. Missing main metrics stay ``NaN``.
    """
    intensity = pd.Series(float("nan"), index=frame.index)
    valid = frame["metric_value"].notna()
    if not valid.any():
        return intensity

    grouped = frame.loc[valid].groupby("event_category")["metric_value"]
    minimum = grouped.transform("min")
    maximum = grouped.transform("max")
    span = maximum - minimum
    scaled = (frame.loc[valid, "metric_value"] - minimum) / span
    intensity.loc[valid] = scaled.where(span > 0, 0.5)
    return intensity


def _text_sizes(frame: pd.DataFrame) -> pd.Series:
    """Scale emoji text size with each phenomenon's configured size range."""
    minimum = frame["event_category"].map({category: style.min_size for category, style in PHENOMENA.items()})
    span = frame["event_category"].map(
        {category: style.max_size - style.min_size for category, style in PHENOMENA.items()}
    )
    return minimum.fillna(8.0) + span.fillna(10.0) * frame["intensity"].fillna(0)


def _format_metric_value(value: float) -> str:
    """Format a metric value for the summary cards and size legend."""
    number = float(value)
    if number.is_integer():
        return f"{number:,.0f}"
    if abs(number) >= 10:
        return f"{number:,.1f}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def _top_region(part: pd.DataFrame) -> tuple[str, int]:
    """Return the state or region with the most POIs for one phenomenon."""
    regions = part["state_province"].dropna().astype(str).str.strip()
    regions = regions[regions != ""]
    if regions.empty:
        return "United States", len(part)
    counts = regions.value_counts()
    return str(counts.index[0]), int(counts.iloc[0])


def _summary_cards_html(frame: pd.DataFrame) -> str:
    """Build one summary card per phenomenon above the map."""
    if frame.empty:
        return ""
    cards = []
    for category in PHENOMENON_ORDER:
        part = frame[frame["event_category"] == category]
        if part.empty:
            continue
        style = PHENOMENA[category]
        values = part["metric_value"].dropna()
        if values.empty:
            mean_value = "No values"
        else:
            mean_value = f"{_format_metric_value(float(values.mean()))} {style.metric_unit}".rstrip()
        region, region_count = _top_region(part)
        cards.append(
            '<div class="us-map-card">'
            f'<div class="us-map-card-header"><span class="us-map-card-emoji">{style.emoji}</span>'
            f'<span class="us-map-card-title">{html.escape(category)}</span></div>'
            f'<div class="us-map-card-count">{len(part):,}</div>'
            '<div class="us-map-card-label">POIs</div>'
            f'<div class="us-map-card-detail"><span>Mean {html.escape(style.metric_name)}</span>'
            f"<strong>{html.escape(mean_value)}</strong></div>"
            '<div class="us-map-card-detail"><span>Top region</span>'
            f"<strong>{html.escape(region)} · {region_count:,}</strong></div>"
            "</div>"
        )
    if not cards:
        return ""
    return f'<div class="us-map-cards">{"".join(cards)}</div>'


def _size_legend_html(frame: pd.DataFrame) -> str:
    """Build the emoji size legend with each phenomenon's observed value range."""
    if frame.empty:
        return ""
    items = []
    for category in PHENOMENON_ORDER:
        part = frame[frame["event_category"] == category]
        if part.empty:
            continue
        style = PHENOMENA[category]
        values = part["metric_value"].dropna()
        if values.empty:
            range_html = (
                f'<span class="us-map-size-emoji" style="font-size:{style.min_size}px">{style.emoji}</span>'
                '<span class="us-map-size-value">no values</span>'
            )
        else:
            low = _format_metric_value(float(values.min()))
            high = _format_metric_value(float(values.max()))
            range_html = (
                f'<span class="us-map-size-emoji" style="font-size:{style.min_size}px">{style.emoji}</span>'
                f'<span class="us-map-size-value">{low}</span>'
                '<span class="us-map-size-arrow">→</span>'
                f'<span class="us-map-size-emoji" style="font-size:{style.max_size}px">{style.emoji}</span>'
                f'<span class="us-map-size-value">{high}</span>'
            )
        items.append(
            '<div class="us-map-size-item">'
            f'<div class="us-map-size-name">{style.emoji} {html.escape(category)}</div>'
            f'<div class="us-map-size-range">{range_html}</div>'
            f'<div class="us-map-size-unit">{html.escape(style.metric_name)} · {html.escape(style.metric_unit)}</div>'
            "</div>"
        )
    if not items:
        return ""
    return (
        '<div class="us-map-size-legend">'
        '<div class="us-map-size-title">Marker size <span>main-metric range in the current selection</span></div>'
        f'<div class="us-map-size-grid">{"".join(items)}</div>'
        "</div>"
    )


def _hover_text(row: object) -> str:
    """Build the HTML hover tooltip for one map point."""
    category = str(getattr(row, "event_category", ""))
    style = PHENOMENA.get(category)
    emoji = style.emoji if style else "📍"
    title = getattr(row, "event_title", None) or category
    location_parts = [
        str(value)
        for value in (getattr(row, "place_location", None), getattr(row, "state_province", None))
        if isinstance(value, str) and value.strip()
    ]
    location = " · ".join(location_parts) or "United States"
    metric_name = getattr(row, "metric_name", "metric")
    metric_value = getattr(row, "metric_value", None)
    metric_unit = getattr(row, "metric_unit", "") or ""
    if pd.notna(metric_value):
        metric = f"{metric_name} = {float(metric_value):,.3g} {metric_unit}".rstrip()
    else:
        metric = f"{metric_name} = no value"
    danger = getattr(row, "danger_rating", None) or "no_rating"
    start = getattr(row, "event_start_date", None)
    end = getattr(row, "event_end_date", None)
    dates = ""
    if pd.notna(start):
        dates = f"{pd.Timestamp(start):%Y-%m-%d}"
        if pd.notna(end):
            dates += f" → {pd.Timestamp(end):%Y-%m-%d}"

    lines = [
        f"<b>{html.escape(emoji)} {html.escape(str(title))}</b>",
        html.escape(location),
        f"Main metric: {html.escape(metric)}",
        f"Danger rating: {html.escape(str(danger))}",
    ]
    if dates:
        lines.append(f"Event: {html.escape(dates)}")
    other_metrics = getattr(row, "other_metrics", None)
    if isinstance(other_metrics, str) and other_metrics.strip():
        other = other_metrics.strip()
        if len(other) > 180:
            other = f"{other[:177]}..."
        lines.append(f"Other: {html.escape(other)}")
    return "<br>".join(lines)


def build_map_figure(frame: pd.DataFrame) -> go.Figure:
    """Build the US phenomenon map.

    Args:
        frame: Map data from :func:`load_map_data`.

    Returns:
        A Plotly geo map with one trace per phenomenon.
    """
    figure = go.Figure()
    if not frame.empty:
        for category in PHENOMENON_ORDER:
            part = frame[frame["event_category"] == category]
            if part.empty:
                continue
            style = PHENOMENA[category]
            valid = part["intensity"].notna()
            if valid.any():
                figure.add_trace(
                    go.Scattergeo(
                        lat=part.loc[valid, "latitude"],
                        lon=part.loc[valid, "longitude"],
                        mode="text",
                        name=f"{style.emoji} {category}",
                        text=[style.emoji] * int(valid.sum()),
                        textfont={"size": part.loc[valid, "text_size"]},
                        hovertext=part.loc[valid, "hover_text"],
                        hoverinfo="text",
                        opacity=0.9,
                    )
                )
            if (~valid).any():
                figure.add_trace(
                    go.Scattergeo(
                        lat=part.loc[~valid, "latitude"],
                        lon=part.loc[~valid, "longitude"],
                        mode="text",
                        name=f"{style.emoji} {category} (no main metric)",
                        text=[style.emoji] * int((~valid).sum()),
                        textfont={"size": style.min_size},
                        hovertext=part.loc[~valid, "hover_text"],
                        hoverinfo="text",
                        showlegend=False,
                        opacity=0.35,
                    )
                )

    if not figure.data:
        figure.add_annotation(
            text="No phenomena match the current filters",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#64748b"},
        )

    figure.update_geos(
        scope="usa",
        projection_type="albers usa",
        showland=True,
        landcolor="#1e293b",
        showocean=True,
        oceancolor="#0f172a",
        showlakes=False,
        showcountries=True,
        countrycolor="#475569",
        showcoastlines=True,
        coastlinecolor="#475569",
        showsubunits=True,
        subunitcolor="#334155",
        bgcolor="rgba(0,0,0,0)",
    )
    figure.update_layout(
        title={
            "text": "Phenomenon locations",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.98,
            "yanchor": "top",
        },
        height=680,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans serif", "size": 13, "color": "#e2e8f0"},
        hovermode="closest",
        hoverlabel={"bgcolor": "#1e293b", "bordercolor": "#334155", "font": {"color": "#e2e8f0"}},
        showlegend=False,
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": "#94a3b8", "activecolor": "#2dd4bf"},
    )
    figure.add_shape(
        type="rect",
        xref="paper",
        yref="paper",
        x0=0.002,
        x1=0.998,
        y0=0.002,
        y1=0.998,
        line={"color": "#64748b", "width": 1.5},
        fillcolor="rgba(0,0,0,0)",
        layer="below",
    )
    return figure


def render() -> None:
    """Render the United States phenomenon map page."""
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    st.markdown(
        "Natural-phenomenon locations across the United States from "
        "`geo.phenomenons_us_vw`. Hover a point for its event, location, main "
        "metric, danger rating and dates."
    )

    try:
        bounds = load_map_date_bounds()
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load the US phenomenon map date bounds: %s", exc)
        st.error("Could not load the US phenomenon map. Check the Supabase connection in the sidebar.")
        return

    if bounds is None:
        st.info("No phenomena are available in the view yet.")
        return

    date_column, category_column = st.columns([1, 1.6])
    date_range = date_column.date_input(
        "Event date range",
        value=bounds,
        min_value=bounds[0],
        max_value=bounds[1],
        format="YYYY-MM-DD",
    )
    selected = category_column.multiselect(
        "Phenomena",
        options=list(PHENOMENON_ORDER),
        default=list(PHENOMENON_ORDER),
        format_func=lambda category: f"{PHENOMENA[category].emoji} {category}",
    )

    if not isinstance(date_range, tuple) or len(date_range) != 2:
        st.info("Select both a start and an end date.")
        return
    start_date, end_date = date_range
    if start_date > end_date:
        st.warning("The start date must not be after the end date.")
        return
    if not selected:
        st.info("Select at least one phenomenon to show on the map.")
        return

    min_magnitude = DEFAULT_MIN_MAGNITUDE
    if "Earthquake" in selected:
        slider_column, _ = st.columns([1, 1.6])
        min_magnitude = slider_column.slider(
            "Minimum earthquake magnitude",
            min_value=0.0,
            max_value=7.0,
            value=DEFAULT_MIN_MAGNITUDE,
            step=0.5,
        )

    try:
        frame = load_map_data(min_magnitude, start_date, end_date)
    except error.QueryTooLargeError:
        st.error(
            "The selected map range is too large. Narrow the date range or raise the earthquake magnitude threshold."
        )
        return
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load the US phenomenon map: %s", exc)
        st.error("Could not load the US phenomenon map. Check the Supabase connection in the sidebar.")
        return

    frame = frame[frame["event_category"].isin(selected)].copy()
    if frame.empty:
        st.info("No phenomena match the current filters.")
        return

    st.markdown(MAP_STYLES, unsafe_allow_html=True)
    st.markdown(_summary_cards_html(frame), unsafe_allow_html=True)
    st.markdown(_size_legend_html(frame), unsafe_allow_html=True)
    st.plotly_chart(build_map_figure(frame), width="stretch")
    st.caption(
        "Marker size shows each phenomenon's main metric intensity, normalised "
        "from its observed minimum to maximum in the current selection. This keeps "
        "different units comparable; emojis identify the phenomenon and hover shows "
        "the actual value."
    )
    if "Earthquake" in selected:
        st.caption(f"Earthquakes below magnitude {min_magnitude:.1f} are hidden by the slider.")
