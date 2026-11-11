"""Reusable natural-phenomenon map dashboard for one geographic area."""

import datetime as dt
import html
import logging
from dataclasses import dataclass
from typing import Final

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import error
from dashboard.map_configs import MapConfig
from utils.database import cached_query
from utils.sql import load_sql

logger = logging.getLogger(__name__)

DEFAULT_MIN_MAGNITUDE: Final = 2.5
MAP_MAX_ROWS: Final = 50_000
MAP_QUERY_TEMPLATE = load_sql("phenomenons_map")
MAP_DATE_BOUNDS_QUERY_TEMPLATE = load_sql("phenomenons_map_date_bounds")

MAP_STYLES: Final = """
<style>
.area-map-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr));
    gap: 0.6rem;
    margin: 0.25rem 0 0.75rem;
}
.area-map-card {
    border: 1px solid #334155;
    border-radius: 0.75rem;
    background: rgba(30, 41, 59, 0.55);
    padding: 0.7rem 0.8rem;
    min-width: 0;
}
.area-map-card-header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.area-map-card-emoji {
    font-size: 1.25rem;
    line-height: 1;
}
.area-map-card-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: #e2e8f0;
}
.area-map-card-count {
    margin-top: 0.35rem;
    font-size: 1.9rem;
    line-height: 1.05;
    font-weight: 700;
    color: #f8fafc;
}
.area-map-card-label {
    font-size: 0.66rem;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #94a3b8;
}
.area-map-card-detail {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin-top: 0.35rem;
    font-size: 0.74rem;
    color: #94a3b8;
}
.area-map-card-detail strong {
    font-size: 0.78rem;
    font-weight: 600;
    color: #cbd5e1;
    text-align: right;
}
.area-map-size-legend {
    border: 1px solid #334155;
    border-radius: 0.75rem;
    background: rgba(30, 41, 59, 0.55);
    padding: 0.7rem 0.9rem;
    margin: 0.25rem 0 0.75rem;
}
.area-map-size-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 0.5rem;
}
.area-map-size-title span {
    font-size: 0.78rem;
    font-weight: 400;
    color: #94a3b8;
}
.area-map-size-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
    align-items: flex-end;
}
.area-map-size-item {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 9rem;
}
.area-map-size-name {
    font-size: 0.78rem;
    font-weight: 600;
    color: #cbd5e1;
}
.area-map-size-range {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
}
.area-map-size-emoji {
    line-height: 1;
}
.area-map-size-value {
    font-size: 0.82rem;
    color: #e2e8f0;
}
.area-map-size-arrow {
    font-size: 0.75rem;
    color: #94a3b8;
}
.area-map-size-unit {
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


@dataclass(frozen=True)
class MapMetadata:
    """Date bounds and categories available in one area view."""

    min_date: dt.date
    max_date: dt.date
    categories: tuple[str, ...]


PHENOMENON_ORDER: Final = (
    "Avalanche",
    "Drought",
    "Earthquake",
    "Fire",
    "Flood",
    "Iceberg",
    "Storm",
    "Volcano",
)

PHENOMENA: Final[dict[str, PhenomenonStyle]] = {
    "Avalanche": PhenomenonStyle("❄️", "size", "destructive size class", 10, 20),
    "Drought": PhenomenonStyle("🌵", "area", "km²", 12, 22),
    "Earthquake": PhenomenonStyle("🏚️", "magnitude", "Mw", 6, 14),
    "Fire": PhenomenonStyle("🔥", "area", "km²", 9, 18),
    "Flood": PhenomenonStyle("🌊", "discharge", "m³/s", 10, 21),
    "Iceberg": PhenomenonStyle("🧊", "surface", "N/m²", 13, 23),
    "Storm": PhenomenonStyle("⛈️", "wind speed", "km/h", 11, 21),
    "Volcano": PhenomenonStyle("🌋", "vei", "VEI", 12, 24),
}

DEFAULT_STYLE: Final = PhenomenonStyle("📍", "metric", "", 8, 18)


def _style(category: str) -> PhenomenonStyle:
    """Return the display style for a phenomenon, with a generic fallback."""
    return PHENOMENA.get(category, DEFAULT_STYLE)


def _order_categories(categories: object) -> tuple[str, ...]:
    """Order available categories by the shared phenomenon order."""
    if isinstance(categories, (list, tuple)):
        names = {str(category) for category in categories if category}
    elif isinstance(categories, str):
        names = {name for name in categories.strip("{}").split(",") if name}
    else:
        names = set()
    known = tuple(category for category in PHENOMENON_ORDER if category in names)
    unknown = tuple(sorted(names.difference(PHENOMENON_ORDER)))
    return known + unknown


def _metadata_query(config: MapConfig) -> str:
    """Fill the metadata SQL template for one area view."""
    return MAP_DATE_BOUNDS_QUERY_TEMPLATE.format(view_name=config.view_name)


def _map_query(config: MapConfig) -> str:
    """Fill the map SQL template for one area view."""
    return MAP_QUERY_TEMPLATE.format(view_name=config.view_name)


def load_map_metadata(config: MapConfig) -> MapMetadata | None:
    """Return date bounds and available categories for one area map.

    Args:
        config: Area map configuration.

    Returns:
        The view metadata, or ``None`` when the view has no dated POIs.
    """
    frame = cached_query(_metadata_query(config))
    if frame.empty:
        return None
    row = frame.iloc[0]
    if pd.isna(row["min_date"]) or pd.isna(row["max_date"]):
        return None
    categories = _order_categories(row["categories"])
    if not categories:
        return None
    return MapMetadata(
        min_date=dt.date.fromisoformat(str(row["min_date"])),
        max_date=dt.date.fromisoformat(str(row["max_date"])),
        categories=categories,
    )


def load_map_data(
    config: MapConfig,
    min_magnitude: float,
    start_date: dt.date,
    end_date: dt.date,
) -> pd.DataFrame:
    """Load one POI per natural-phenomenon event for one area.

    Args:
        config: Area map configuration.
        min_magnitude: Minimum earthquake magnitude to include.
        start_date: First event start date to include.
        end_date: Last event start date to include (inclusive).

    Returns:
        A DataFrame with location, metric, event and hover fields.
    """
    frame = cached_query(
        _map_query(config),
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
    return minimum.fillna(DEFAULT_STYLE.min_size) + span.fillna(
        DEFAULT_STYLE.max_size - DEFAULT_STYLE.min_size
    ) * frame["intensity"].fillna(0)


def _format_metric_value(value: float) -> str:
    """Format a metric value for the summary cards and size legend."""
    number = float(value)
    if number.is_integer():
        return f"{number:,.0f}"
    if abs(number) >= 10:
        return f"{number:,.1f}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def _top_region(part: pd.DataFrame, config: MapConfig) -> tuple[str, int]:
    """Return the configured country, state or area with the most POIs."""
    regions = part[config.region_field].dropna().astype(str).str.strip()
    regions = regions[(regions != "") & (regions.str.lower() != "nan")]
    if regions.empty:
        return config.fallback_region, len(part)
    counts = regions.value_counts()
    return str(counts.index[0]), int(counts.iloc[0])


def _summary_cards_html(frame: pd.DataFrame, config: MapConfig) -> str:
    """Build one summary card per phenomenon above the map."""
    if frame.empty:
        return ""
    cards = []
    for category in _order_categories(frame["event_category"].unique().tolist()):
        part = frame[frame["event_category"] == category]
        if part.empty:
            continue
        style = _style(category)
        values = part["metric_value"].dropna()
        if values.empty:
            mean_value = "No values"
        else:
            mean_value = f"{_format_metric_value(float(values.mean()))} {style.metric_unit}".rstrip()
        region, region_count = _top_region(part, config)
        cards.append(
            '<div class="area-map-card">'
            f'<div class="area-map-card-header"><span class="area-map-card-emoji">{style.emoji}</span>'
            f'<span class="area-map-card-title">{html.escape(category)}</span></div>'
            f'<div class="area-map-card-count">{len(part):,}</div>'
            '<div class="area-map-card-label">POIs</div>'
            f'<div class="area-map-card-detail"><span>Mean {html.escape(style.metric_name)}</span>'
            f"<strong>{html.escape(mean_value)}</strong></div>"
            f'<div class="area-map-card-detail"><span>{html.escape(config.region_label)}</span>'
            f"<strong>{html.escape(region)} · {region_count:,}</strong></div>"
            "</div>"
        )
    if not cards:
        return ""
    return f'<div class="area-map-cards">{"".join(cards)}</div>'


def _size_legend_html(frame: pd.DataFrame) -> str:
    """Build the emoji size legend with each phenomenon's observed value range."""
    if frame.empty:
        return ""
    items = []
    for category in _order_categories(frame["event_category"].unique().tolist()):
        part = frame[frame["event_category"] == category]
        if part.empty:
            continue
        style = _style(category)
        values = part["metric_value"].dropna()
        if values.empty:
            range_html = (
                f'<span class="area-map-size-emoji" style="font-size:{style.min_size}px">{style.emoji}</span>'
                '<span class="area-map-size-value">no values</span>'
            )
        else:
            low = _format_metric_value(float(values.min()))
            high = _format_metric_value(float(values.max()))
            range_html = (
                f'<span class="area-map-size-emoji" style="font-size:{style.min_size}px">{style.emoji}</span>'
                f'<span class="area-map-size-value">{low}</span>'
                '<span class="area-map-size-arrow">→</span>'
                f'<span class="area-map-size-emoji" style="font-size:{style.max_size}px">{style.emoji}</span>'
                f'<span class="area-map-size-value">{high}</span>'
            )
        items.append(
            '<div class="area-map-size-item">'
            f'<div class="area-map-size-name">{style.emoji} {html.escape(category)}</div>'
            f'<div class="area-map-size-range">{range_html}</div>'
            f'<div class="area-map-size-unit">{html.escape(style.metric_name)} · {html.escape(style.metric_unit)}</div>'
            "</div>"
        )
    if not items:
        return ""
    return (
        '<div class="area-map-size-legend">'
        '<div class="area-map-size-title">Marker size <span>main-metric range in the current selection</span></div>'
        f'<div class="area-map-size-grid">{"".join(items)}</div>'
        "</div>"
    )


def _hover_text(row: object) -> str:
    """Build the HTML hover tooltip for one map point."""
    category = str(getattr(row, "event_category", ""))
    style = _style(category)
    emoji = style.emoji
    title = getattr(row, "event_title", None) or category
    location_parts = [
        str(value)
        for value in (getattr(row, "place_location", None), getattr(row, "state_province", None))
        if isinstance(value, str) and value.strip()
    ]
    location = " · ".join(location_parts) or "Unknown location"
    metric_name = getattr(row, "metric_name", None) or style.metric_name
    metric_value = getattr(row, "metric_value", None)
    metric_unit = getattr(row, "metric_unit", None) or ""
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


def _plot_longitudes(part: pd.DataFrame, config: MapConfig) -> pd.Series:
    """Return longitudes suitable for dateline-wrapping projections."""
    longitude = part["longitude"]
    if config.wrap_longitude:
        return longitude.where(longitude >= 0, longitude + 360.0)
    return longitude


def build_map_figure(frame: pd.DataFrame, config: MapConfig) -> go.Figure:
    """Build one area phenomenon map.

    Args:
        frame: Map data from :func:`load_map_data`.
        config: Area map configuration.

    Returns:
        A framed Plotly geo map with one trace per phenomenon.
    """
    figure = go.Figure()
    if not frame.empty:
        for category in _order_categories(frame["event_category"].unique().tolist()):
            part = frame[frame["event_category"] == category]
            if part.empty:
                continue
            style = _style(category)
            valid = part["intensity"].notna()
            if valid.any():
                figure.add_trace(
                    go.Scattergeo(
                        lat=part.loc[valid, "latitude"],
                        lon=_plot_longitudes(part.loc[valid], config),
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
                        lon=_plot_longitudes(part.loc[~valid], config),
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

    geo_layout: dict[str, object] = {
        "scope": config.scope,
        "projection_type": config.projection,
        "showland": True,
        "landcolor": "#1e293b",
        "showocean": True,
        "oceancolor": "#0f172a",
        "showlakes": False,
        "showcountries": True,
        "countrycolor": "#475569",
        "showcoastlines": True,
        "coastlinecolor": "#475569",
        "showsubunits": True,
        "subunitcolor": "#334155",
        "bgcolor": "rgba(0,0,0,0)",
    }
    if config.lon_range is not None:
        geo_layout["lonaxis"] = {"range": list(config.lon_range)}
    if config.lat_range is not None:
        geo_layout["lataxis"] = {"range": list(config.lat_range)}
    if config.rotation is not None:
        geo_layout["projection_rotation"] = {"lon": config.rotation[0], "lat": config.rotation[1]}
    figure.update_geos(**geo_layout)
    figure.update_layout(
        height=680,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
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


def render_map(config: MapConfig) -> None:
    """Render one area phenomenon map page.

    Args:
        config: Area map configuration.
    """
    st.title(f"{config.icon} {config.title}")
    st.markdown(config.description)
    st.subheader(config.locations_title)

    try:
        metadata = load_map_metadata(config)
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load %s map metadata: %s", config.nav_label, exc)
        st.error(f"Could not load the {config.nav_label} phenomenon map. Check the Supabase connection in the sidebar.")
        return

    if metadata is None:
        st.info(f"No phenomena are available in {config.view_name} yet.")
        return

    date_column, category_column = st.columns([1, 1.6])
    date_range = date_column.date_input(
        "Event date range",
        value=(metadata.min_date, metadata.max_date),
        min_value=metadata.min_date,
        max_value=metadata.max_date,
        format="YYYY-MM-DD",
    )
    selected = category_column.multiselect(
        "Phenomena",
        options=list(metadata.categories),
        default=list(metadata.categories),
        format_func=lambda category: f"{_style(category).emoji} {category}",
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
        frame = load_map_data(config, min_magnitude, start_date, end_date)
    except error.QueryTooLargeError:
        st.error(
            "The selected map range is too large. Narrow the date range or raise the earthquake magnitude threshold."
        )
        return
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load the %s phenomenon map: %s", config.nav_label, exc)
        st.error(f"Could not load the {config.nav_label} phenomenon map. Check the Supabase connection in the sidebar.")
        return

    frame = frame[frame["event_category"].isin(selected)].copy()
    if frame.empty:
        st.info("No phenomena match the current filters.")
        return

    st.markdown(MAP_STYLES, unsafe_allow_html=True)
    st.markdown(_summary_cards_html(frame, config), unsafe_allow_html=True)
    st.plotly_chart(build_map_figure(frame, config), width="stretch")
    st.markdown(_size_legend_html(frame), unsafe_allow_html=True)
    st.caption(
        "Marker size shows each phenomenon's main metric intensity, normalised "
        "from its observed minimum to maximum in the current selection. This keeps "
        "different units comparable; emojis identify the phenomenon and hover shows "
        "the actual value."
    )
    if "Earthquake" in selected:
        st.caption(f"Earthquakes below magnitude {min_magnitude:.1f} are hidden by the slider.")
