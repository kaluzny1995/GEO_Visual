"""Drought metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="drought",
    view_name="geo.metrics_drought_vw",
    page_title="Drought metrics timeline & distribution",
    page_icon="🌵",
    description="drought metrics",
    date_bounds_query=load_sql("drought_metrics_date_bounds"),
    timeline_query=load_sql("drought_metrics_timeline"),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the drought metrics timeline page."""
    render_dashboard(DASHBOARD)
