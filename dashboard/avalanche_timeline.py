"""Avalanche metrics timeline dashboard configuration."""

from dashboard.metrics_timeline import DashboardConfig, render_dashboard
from utils.sql import load_sql

DASHBOARD = DashboardConfig(
    key="avalanche",
    view_name="geo.metrics_avalanche_vw",
    page_title="Avalanche metrics timeline",
    page_icon="❄️",
    description="avalanche metrics",
    date_bounds_query=load_sql("avalanche_metrics_date_bounds"),
    timeline_query=load_sql("avalanche_metrics_timeline"),
    note_metric="danger_level",
    note=(
        "NAPADS `danger_level = -1` means *no rating*; it is plotted as recorded so off-season snapshots stay visible."
    ),
)

PAGE_TITLE = DASHBOARD.page_title
PAGE_ICON = DASHBOARD.page_icon


def render() -> None:
    """Render the avalanche metrics timeline page."""
    render_dashboard(DASHBOARD)
