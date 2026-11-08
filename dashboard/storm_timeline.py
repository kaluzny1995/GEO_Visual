"""Storm metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="storm",
    view_name="geo.metrics_storm_vw",
    page_title="Storm metrics timeline",
    page_icon="⛈️",
    description="storm metrics",
    date_bounds_query=load_sql("storm_metrics_date_bounds"),
    timeline_query=load_sql("storm_metrics_timeline"),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the storm metrics timeline page."""
    render_dashboard(DASHBOARD)
