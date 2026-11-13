"""Reusable natural-phenomenon map dashboard for one geographic area."""

import datetime as dt
import html
import logging
import re
from dataclasses import dataclass
from numbers import Real
from typing import Final

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import error
from dashboard.map_configs import MapConfig
from dashboard.region_names import (
    contains_subdivision_name,
    country_name,
    region_name,
    subdivision_name,
)
from utils.database import DB_CONFIG, cached_query
from utils.sql import load_sql

logger = logging.getLogger(__name__)

DEFAULT_MIN_MAGNITUDE: Final = DB_CONFIG.map_default_min_magnitude
MAP_MAX_ROWS: Final = DB_CONFIG.map_max_rows
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
.area-map-color-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-top: 0.2rem;
}
.area-map-color-bar {
    width: 4.5rem;
    height: 0.35rem;
    border: 1px solid #475569;
    border-radius: 999px;
}
.area-map-color-label {
    font-size: 0.66rem;
    color: #94a3b8;
}
</style>
"""


@dataclass(frozen=True)
class PhenomenonStyle:
    """Display and map style for one phenomenon.

    Attributes:
        emoji: Emoji shown in the legend, hover text, selector and map.
        metric_name: Main metric used for marker size and colour.
        metric_unit: Unit of the main metric.
        min_size: Emoji font size for the lowest observed main metric value.
        max_size: Emoji font size for the highest observed main metric value.
        colors: Low, middle and high colours for the metric's colour scale.
    """

    emoji: str
    metric_name: str
    metric_unit: str
    min_size: int
    max_size: int
    colors: tuple[str, str, str]


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
    "Avalanche": PhenomenonStyle("❄️", "size", "destructive size class", 10, 20, ("#e0f2fe", "#38bdf8", "#2563eb")),
    "Drought": PhenomenonStyle("🌵", "area", "km²", 12, 22, ("#fef3c7", "#fbbf24", "#d97706")),
    "Earthquake": PhenomenonStyle("🏚️", "magnitude", "Mw", 6, 14, ("#ede9fe", "#a78bfa", "#7c3aed")),
    "Fire": PhenomenonStyle("🔥", "area", "km²", 9, 18, ("#fef9c3", "#fb923c", "#ef4444")),
    "Flood": PhenomenonStyle("🌊", "discharge", "m³/s", 10, 21, ("#cffafe", "#22d3ee", "#3b82f6")),
    "Iceberg": PhenomenonStyle("🧊", "surface", "N/m²", 13, 23, ("#ecfeff", "#67e8f9", "#06b6d4")),
    "Storm": PhenomenonStyle("⛈️", "wind speed", "km/h", 11, 21, ("#ccfbf1", "#2dd4bf", "#0d9488")),
    "Volcano": PhenomenonStyle("🌋", "vei", "VEI", 12, 24, ("#fde68a", "#fb923c", "#f43f5e")),
}

DEFAULT_STYLE: Final = PhenomenonStyle("📍", "metric", "", 8, 18, ("#cbd5e1", "#94a3b8", "#475569"))

FIELD_LABELS: Final[dict[str, str]] = {
    "area": "Area",
    "baseline_days": "Baseline days",
    "baseline_end": "Baseline end",
    "baseline_start": "Baseline start",
    "casualties": "Casualties",
    "damage": "Damage",
    "depth": "Depth",
    "direction": "Direction",
    "discharge": "Discharge",
    "dist2land": "Distance to land",
    "exceedance_ratio": "Exceedance ratio",
    "geometry_count": "Geometry count",
    "gust": "Gust",
    "landfall": "Landfall",
    "magnitude": "Magnitude",
    "nst": "Stations",
    "percent_contained": "Percent contained",
    "pressure": "Pressure",
    "saffir_simpson": "Saffir-Simpson",
    "size": "Size",
    "speed": "Speed",
    "surface": "Surface",
    "threshold": "Threshold",
    "threshold_exceeded": "Threshold exceeded",
    "vei": "VEI",
    "vnum": "Volcano number",
    "wind speed": "Wind speed",
}


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
    frame["hover_color"] = [
        _metric_text_color(_style(category), intensity)
        for category, intensity in zip(frame["event_category"], frame["intensity"], strict=True)
    ]
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


def _field_label(name: object) -> str:
    """Return a human-readable field name with spaces instead of underscores."""
    raw = str(name).strip().lower()
    label = FIELD_LABELS.get(raw)
    if label is None:
        normalized = raw.replace("_", " ").strip()
        label = FIELD_LABELS.get(normalized)
    if label is None:
        normalized = raw.replace("_", " ").strip()
        label = normalized[:1].upper() + normalized[1:]
    return label


def _display_value(value: object) -> str:
    """Replace underscores in a value and normalise whitespace for display."""
    text = re.sub(r"\s+", " ", str(value).replace("_", " ")).strip()
    if text.lower() in {"true", "false"}:
        return text.capitalize()
    return text


def _should_hide_metric(name: object) -> bool:
    """Return whether a secondary metric is a percentile or danger-related."""
    normalized = str(name).strip().lower()
    return (
        "danger" in normalized
        or "alert" in normalized
        or "color_code" in normalized
        or "colour_code" in normalized
        or "percentile" in normalized
        or re.search(r"_p\d+$", normalized) is not None
    )


def _string_value(value: object, default: str) -> str:
    """Return a non-empty string value or a default."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


PLACE_ABBREVIATIONS: Final[dict[str, str]] = {
    "DRC": "Democratic Republic of the Congo",
    "UK": "United Kingdom",
    "USA": "United States",
}


def _replace_region_codes(text: str, country_code: object, state_province: object) -> str:
    """Replace country, abbreviation and region codes in safe display positions."""
    for abbreviation, full_name in PLACE_ABBREVIATIONS.items():
        text = re.sub(rf"\b{re.escape(abbreviation)}\b", full_name, text)

    country = country_name(country_code)
    country_code_text = _string_value(country_code, "").upper()
    subdivision = subdivision_name(country_code, state_province)
    subdivision_code = _string_value(state_province, "").upper()

    def replace_code(match: re.Match[str]) -> str:
        code = match.group(1)
        if code == country_code_text and country:
            return match.group(0).replace(code, country)
        candidate = subdivision_name(country_code, code)
        if candidate:
            return match.group(0).replace(code, candidate)
        if code == subdivision_code and subdivision:
            return match.group(0).replace(code, subdivision)
        return match.group(0)

    text = re.sub(r" - ([A-Z]{2,3})(:?)$", replace_code, text)
    text = re.sub(r",\s*([A-Z]{2,3})$", replace_code, text)
    stripped = text.strip()
    if stripped.upper() == country_code_text and country:
        return country
    if stripped.upper() == subdivision_code and subdivision:
        return subdivision
    return text


def _display_event_title(value: object, country_code: object, state_province: object) -> str:
    """Clean an event title and replace embedded region codes with full names."""
    title = _replace_region_codes(_display_value(value), country_code, state_province)
    return title.rstrip(":").strip()


def _other_metrics_lines(value: object) -> list[str]:
    """Split a compact other-metrics string into one display line per metric."""
    if not isinstance(value, str) or not value.strip():
        return []
    lines = []
    for chunk in value.split(";"):
        if ":" not in chunk:
            continue
        name, metric_value = chunk.split(":", 1)
        name = name.strip()
        metric_value = metric_value.strip()
        if not name or not metric_value or _should_hide_metric(name):
            continue
        lines.append(f"{_field_label(name)}: {_display_value(metric_value)}")
    return lines


def _location_text(row: object) -> str:
    """Return a location string with full country and region names."""
    country_code = getattr(row, "country_code", None)
    state_province = getattr(row, "state_province", None)
    country = country_name(country_code)
    region = region_name(country_code, state_province)
    place = _replace_region_codes(
        _display_value(getattr(row, "place_location", None) or ""),
        country_code,
        state_province,
    )
    if place.lower() in {"", "none", "nan", "<na>"}:
        return region or "Unknown location"
    if not region:
        return place
    if place.casefold() == region.casefold() or place.casefold() == country.casefold():
        return region
    if contains_subdivision_name(country_code, place):
        if country and country.casefold() not in place.casefold():
            return f"{place} · {country}"
        return place
    if country and country.casefold() in place.casefold():
        if "," in place:
            return place
        province = region.removeprefix(f"{country} - ")
        return f"{place} · {province}" if province != region else place
    return f"{place} · {region}"


def _interpolate_color(style: PhenomenonStyle, position: float) -> str:
    """Interpolate a phenomenon's three-colour text scale at a 0-1 position."""
    position = min(max(float(position), 0.0), 1.0)
    if position <= 0.5:
        start, end = style.colors[0], style.colors[1]
        local = position / 0.5
    else:
        start, end = style.colors[1], style.colors[2]
        local = (position - 0.5) / 0.5
    start_rgb = [int(start[index : index + 2], 16) for index in (1, 3, 5)]
    end_rgb = [int(end[index : index + 2], 16) for index in (1, 3, 5)]
    mixed = [round(first + (second - first) * local) for first, second in zip(start_rgb, end_rgb, strict=True)]
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def _metric_text_color(style: PhenomenonStyle, intensity: object) -> str:
    """Return the metric-scale text colour for one point's intensity."""
    if not isinstance(intensity, Real):
        return "#cbd5e1"
    value = float(intensity)
    if pd.isna(value):
        return "#cbd5e1"
    return _interpolate_color(style, value)


def _value_intensity(values: pd.Series, value: float) -> float:
    """Return a value's 0-1 position within its phenomenon's observed range."""
    low = float(values.min())
    high = float(values.max())
    if high <= low:
        return 0.5
    return (float(value) - low) / (high - low)


def _top_region(part: pd.DataFrame, config: MapConfig) -> tuple[str, int]:
    """Return the configured country, state or area with the most POIs."""
    if config.region_field == "state_province":
        regions = part.apply(
            lambda row: region_name(row["country_code"], row["state_province"]),
            axis=1,
        ).astype(str)
    elif config.region_field == "country_code":
        regions = part["country_code"].map(country_name).astype(str)
    else:
        regions = part["place_location"].map(_display_value).astype(str)

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
            mean_color = "#94a3b8"
        else:
            mean = float(values.mean())
            mean_value = f"{_format_metric_value(mean)} {style.metric_unit}".rstrip()
            mean_color = _interpolate_color(style, _value_intensity(values, mean))
        region, region_count = _top_region(part, config)
        cards.append(
            '<div class="area-map-card">'
            f'<div class="area-map-card-header"><span class="area-map-card-emoji">{style.emoji}</span>'
            f'<span class="area-map-card-title">{html.escape(category)}</span></div>'
            f'<div class="area-map-card-count">{len(part):,}</div>'
            '<div class="area-map-card-label">POIs</div>'
            f'<div class="area-map-card-detail"><span>Mean {html.escape(style.metric_name)}</span>'
            f'<strong style="color:{mean_color}">{html.escape(mean_value)}</strong></div>'
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
                f'<span class="area-map-size-value" style="color:{style.colors[0]}">{low}</span>'
                '<span class="area-map-size-arrow">→</span>'
                f'<span class="area-map-size-emoji" style="font-size:{style.max_size}px">{style.emoji}</span>'
                f'<span class="area-map-size-value" style="color:{style.colors[2]}">{high}</span>'
            )
        items.append(
            '<div class="area-map-size-item">'
            f'<div class="area-map-size-name">{style.emoji} {html.escape(category)}</div>'
            f'<div class="area-map-size-range">{range_html}</div>'
            f'<div class="area-map-size-unit">{html.escape(_field_label(style.metric_name))} · '
            f"{html.escape(style.metric_unit)}</div>"
            '<div class="area-map-color-row">'
            f'<span class="area-map-color-bar" style="background:linear-gradient(90deg,'
            f'{",".join(style.colors)});"></span>'
            '<span class="area-map-color-label">Text colour: low → high</span></div>'
            "</div>"
        )
    if not items:
        return ""
    return (
        '<div class="area-map-size-legend">'
        '<div class="area-map-size-title">Marker size &amp; text colour '
        "<span>main-metric range and text colour scale in the current selection</span></div>"
        f'<div class="area-map-size-grid">{"".join(items)}</div>'
        "</div>"
    )


def _hover_text(row: object) -> str:
    """Build the HTML hover tooltip for one map point."""
    category = str(getattr(row, "event_category", ""))
    style = _style(category)
    country_code = getattr(row, "country_code", None)
    state_province = getattr(row, "state_province", None)
    title = _display_event_title(
        _string_value(getattr(row, "event_title", None), category),
        country_code,
        state_province,
    )
    location = _location_text(row)
    metric_name = _string_value(getattr(row, "metric_name", None), style.metric_name)
    metric_value = getattr(row, "metric_value", None)
    metric_unit = _string_value(getattr(row, "metric_unit", None), style.metric_unit)
    if pd.notna(metric_value):
        metric = f"{_format_metric_value(float(metric_value))} {_display_value(metric_unit)}".strip()
    else:
        metric = "No value"
    start = getattr(row, "event_start_date", None)
    end = getattr(row, "event_end_date", None)
    dates = ""
    if pd.notna(start):
        dates = f"{pd.Timestamp(start):%Y-%m-%d}"
        if pd.notna(end):
            dates += f" → {pd.Timestamp(end):%Y-%m-%d}"

    lines = [
        f"<b>{html.escape(style.emoji)} {html.escape(title)}</b>",
        html.escape(location),
        f"{html.escape(_field_label(metric_name))}: {html.escape(metric)}",
    ]
    lines.extend(html.escape(line) for line in _other_metrics_lines(getattr(row, "other_metrics", None)))
    if dates:
        lines.append(f"Event: {html.escape(dates)}")
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
                        hoverlabel={"font": {"color": part.loc[valid, "hover_color"].tolist()}},
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
                        hoverlabel={"font": {"color": part.loc[~valid, "hover_color"].tolist()}},
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
        "from its observed minimum to maximum in the current selection. Emojis keep "
        "their native colours; tooltip, card and legend text use the phenomenon's "
        "metric colour scale, and hover shows the actual value."
    )
    if "Earthquake" in selected:
        st.caption(f"Earthquakes below magnitude {min_magnitude:.1f} are hidden by the slider.")
