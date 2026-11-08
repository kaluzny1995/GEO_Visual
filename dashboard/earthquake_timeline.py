"""Earthquake metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="earthquake",
    view_name="geo.metrics_earthquake_vw",
    page_title="Earthquake metrics timeline",
    page_icon="🏚️",
    description="earthquake metrics",
    date_bounds_query=load_sql("earthquake_metrics_date_bounds"),
    timeline_query=load_sql("earthquake_metrics_timeline"),
    hidden_metrics=(("magnitude", "mlr"),),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the earthquake metrics timeline page."""
    render_dashboard(DASHBOARD)
