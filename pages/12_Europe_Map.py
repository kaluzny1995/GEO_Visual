"""Streamlit page: Europe phenomenon map."""

from dashboard.map_configs import MAP_CONFIGS_BY_KEY
from dashboard.phenomenon_map import render_map
from utils.layout import CONFIG, configure_page, render_sidebar

MAP = MAP_CONFIGS_BY_KEY["europe"]

configure_page(page_title=f"{MAP.title} · {CONFIG.app.title}", page_icon=MAP.icon)
render_sidebar()
render_map(MAP)
