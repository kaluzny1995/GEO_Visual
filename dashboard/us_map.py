"""United States phenomenon map dashboard."""

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
PAGE_ICON = "🗺️"
DEFAULT_MIN_MAGNITUDE: Final = 2.5
MAP_MAX_ROWS: Final = 50_000
MAP_QUERY = load_sql("phenomenons_us_map")


@dataclass(frozen=True)
class PhenomenonStyle:
    """Display and map style for one phenomenon.

    Attributes:
        emoji: Emoji shown in the legend, hover text, selector and map.
        metric_name: Main metric used for marker size.
        metric_unit: Unit of the main metric.
    """

    emoji: str
    metric_name: str
    metric_unit: str


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
    "Avalanche": PhenomenonStyle("❄️", "size", "destructive size class"),
    "Drought": PhenomenonStyle("🌵", "area", "km²"),
    "Earthquake": PhenomenonStyle("🏚️", "magnitude", "Mw"),
    "Fire": PhenomenonStyle("🔥", "area", "km²"),
    "Flood": PhenomenonStyle("🌊", "discharge", "m³/s"),
    "Storm": PhenomenonStyle("⛈️", "wind speed", "km/h"),
    "Volcano": PhenomenonStyle("🌋", "vei", "VEI"),
}


def load_map_data(min_magnitude: float) -> pd.DataFrame:
    """Load one POI per natural-phenomenon event.

    Args:
        min_magnitude: Minimum earthquake magnitude to include.

    Returns:
        A DataFrame with location, metric, event and hover fields.
    """
    frame = cached_query(
        MAP_QUERY,
        (("min_magnitude", min_magnitude),),
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
    """Scale emoji text size with the normalised main metric value."""
    base = pd.Series(8.0, index=frame.index)
    span = pd.Series(10.0, index=frame.index)
    earthquake = frame["event_category"].eq("Earthquake")
    base.loc[earthquake] = 6.0
    span.loc[earthquake] = 8.0
    return base + span * frame["intensity"].fillna(0)


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
                        textfont={"size": 6},
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
        domain={"x": [0, 0.9], "y": [0, 1]},
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
        margin={"l": 8, "r": 8, "t": 80, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans serif", "size": 13, "color": "#e2e8f0"},
        hovermode="closest",
        hoverlabel={"bgcolor": "#1e293b", "bordercolor": "#334155", "font": {"color": "#e2e8f0"}},
        showlegend=False,
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": "#94a3b8", "activecolor": "#2dd4bf"},
    )
    figure.add_annotation(
        text="Marker size",
        xref="paper",
        yref="paper",
        x=0.92,
        y=0.31,
        xanchor="left",
        yanchor="middle",
        showarrow=False,
        font={"size": 12, "color": "#94a3b8"},
    )
    for label, size, y_position in (("Low", 8, 0.24), ("Medium", 13, 0.17), ("High", 18, 0.09)):
        figure.add_annotation(
            text="●",
            xref="paper",
            yref="paper",
            x=0.92,
            y=y_position,
            xanchor="left",
            yanchor="middle",
            showarrow=False,
            font={"size": size, "color": "#e2e8f0"},
        )
        figure.add_annotation(
            text=label,
            xref="paper",
            yref="paper",
            x=0.945,
            y=y_position,
            xanchor="left",
            yanchor="middle",
            showarrow=False,
            font={"size": 11, "color": "#cbd5e1"},
        )
    return figure


def _legend_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Build the phenomenon legend and observed main-metric ranges."""
    rows = []
    for category in PHENOMENON_ORDER:
        part = frame[frame["event_category"] == category]
        if part.empty:
            continue
        style = PHENOMENA[category]
        values = part["metric_value"].dropna()
        if values.empty:
            observed_range = "No values"
        else:
            observed_range = f"{values.min():,.3g} to {values.max():,.3g} {style.metric_unit}"
        rows.append(
            {
                "Emoji": style.emoji,
                "Phenomenon": category,
                "Main metric": f"{style.metric_name} ({style.metric_unit})",
                "Observed range": observed_range,
                "POIs": len(part),
            }
        )
    return pd.DataFrame(rows)


def render() -> None:
    """Render the United States phenomenon map page."""
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    st.markdown(
        "Natural-phenomenon locations across the United States from "
        "`geo.phenomenons_us_vw`. Hover a point for its event, location, main "
        "metric, danger rating and dates."
    )

    category_column, magnitude_column = st.columns([2, 1])
    selected = category_column.multiselect(
        "Phenomena",
        options=list(PHENOMENON_ORDER),
        default=list(PHENOMENON_ORDER),
        format_func=lambda category: f"{PHENOMENA[category].emoji} {category}",
    )
    min_magnitude = DEFAULT_MIN_MAGNITUDE
    if "Earthquake" in selected:
        min_magnitude = magnitude_column.slider(
            "Minimum earthquake magnitude",
            min_value=0.0,
            max_value=7.0,
            value=DEFAULT_MIN_MAGNITUDE,
            step=0.5,
        )
    if not selected:
        st.info("Select at least one phenomenon to show on the map.")
        return

    try:
        frame = load_map_data(min_magnitude)
    except error.QueryTooLargeError:
        st.error("The selected map range is too large. Raise the earthquake magnitude threshold.")
        return
    except Exception as exc:  # UI boundary: any failure becomes a page message.
        logger.warning("Could not load the US phenomenon map: %s", exc)
        st.error("Could not load the US phenomenon map. Check the Supabase connection in the sidebar.")
        return

    frame = frame[frame["event_category"].isin(selected)].copy()
    if frame.empty:
        st.info("No phenomena match the current filters.")
        return

    st.plotly_chart(build_map_figure(frame), width="stretch")
    st.caption(
        "Marker size shows each phenomenon's main metric intensity, normalised "
        "from its observed minimum to maximum in the current selection. This keeps "
        "different units comparable; emojis identify the phenomenon and hover shows "
        "the actual value."
    )
    if "Earthquake" in selected:
        st.caption(f"Earthquakes below magnitude {min_magnitude:.1f} are hidden by the slider.")
    st.dataframe(_legend_frame(frame), hide_index=True)
