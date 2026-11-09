"""Flood metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="flood",
    view_name="geo.metrics_flood_vw",
    page_title="Flood metrics timeline & distribution",
    page_icon="🌊",
    description="flood metrics",
    date_bounds_query=load_sql("flood_metrics_date_bounds"),
    timeline_query=load_sql("flood_metrics_timeline"),
    hidden_metrics=(("baseline_days", None), ("magnitude", None)),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the flood metrics timeline page."""
    render_dashboard(DASHBOARD)
