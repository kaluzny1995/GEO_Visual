"""Streamlit page: iceberg metrics timeline."""

from dashboard.iceberg_timeline import PAGE_ICON, PAGE_TITLE, render
from utils.layout import CONFIG, configure_page, render_sidebar

configure_page(page_title=f"{PAGE_TITLE} · {CONFIG.app.title}", page_icon=PAGE_ICON)
render_sidebar()
render()
