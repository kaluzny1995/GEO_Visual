"""Iceberg metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="iceberg",
    view_name="geo.metrics_iceberg_vw",
    page_title="Iceberg metrics timeline & distribution",
    page_icon="🧊",
    description="iceberg metrics",
    date_bounds_query=load_sql("iceberg_metrics_date_bounds"),
    timeline_query=load_sql("iceberg_metrics_timeline"),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the iceberg metrics timeline page."""
    render_dashboard(DASHBOARD)
