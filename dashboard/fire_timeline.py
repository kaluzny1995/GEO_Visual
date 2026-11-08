"""Fire metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="fire",
    view_name="geo.metrics_fire_vw",
    page_title="Fire metrics timeline",
    page_icon="🔥",
    description="fire metrics",
    date_bounds_query=load_sql("fire_metrics_date_bounds"),
    timeline_query=load_sql("fire_metrics_timeline"),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the fire metrics timeline page."""
    render_dashboard(DASHBOARD)
