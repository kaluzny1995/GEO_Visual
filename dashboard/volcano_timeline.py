"""Volcano metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="volcano",
    view_name="geo.metrics_volcano_vw",
    page_title="Volcano metrics timeline",
    page_icon="🌋",
    description="volcano metrics",
    date_bounds_query=load_sql("volcano_metrics_date_bounds"),
    timeline_query=load_sql("volcano_metrics_timeline"),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the volcano metrics timeline page."""
    render_dashboard(DASHBOARD)
