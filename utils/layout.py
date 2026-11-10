"""Shared Streamlit page setup and sidebar."""

from pathlib import Path

import streamlit as st

from dashboard.catalog import DASHBOARDS, MAPS
from model.config.app_config import AppConfig
from utils.database import cached_connection_status, clear_connection_cache

# Loaded once per page; a config change requires a Streamlit restart.
CONFIG = AppConfig.from_json()
PROJECT_DIR = Path(__file__).resolve().parents[1]


def configure_page(*, page_title: str | None = None, page_icon: str | None = None) -> None:
    """Configure the browser tab and page layout shared by every page.

    Must run before any other Streamlit command on a page.

    Args:
        page_title: Browser tab title. Defaults to the application title.
        page_icon: Browser tab icon. Defaults to the application icon.
    """
    st.set_page_config(
        page_title=page_title or CONFIG.app.title,
        page_icon=page_icon or CONFIG.app.page_icon,
        layout=CONFIG.app.layout,
    )


def render_sidebar() -> None:
    """Render navigation, branding, the version and the Supabase connection status."""
    with st.sidebar:
        st.page_link(
            st.Page(str(PROJECT_DIR / "app.py"), title="Start", icon="🌍"),
            label="Start",
            icon="🌍",
        )
        with st.expander("Metric timelines and distributions", expanded=True):
            for dashboard in DASHBOARDS:
                st.page_link(
                    st.Page(
                        str(PROJECT_DIR / dashboard.page_path),
                        title=dashboard.nav_label,
                        icon=dashboard.icon,
                    ),
                    label=dashboard.nav_label,
                    icon=dashboard.icon,
                )
        with st.expander("Phenomenon maps", expanded=True):
            for map_page in MAPS:
                st.page_link(
                    st.Page(
                        str(PROJECT_DIR / map_page.page_path),
                        title=map_page.nav_label,
                        icon=map_page.icon,
                    ),
                    label=map_page.nav_label,
                    icon=map_page.icon,
                )
        st.divider()

        st.title(f"{CONFIG.app.page_icon} {CONFIG.app.title}")
        st.caption(f"Version {CONFIG.app.version}")
        st.divider()

        st.subheader("Supabase")
        status = cached_connection_status()
        if status.connected:
            st.success(status.message)
        else:
            st.warning(status.message)
        if st.button("Recheck connection"):
            clear_connection_cache()
            st.rerun()
        st.caption("Credentials are read from `.env` (`SUPABASE_DB_*`).")
        st.divider()
        st.caption("Python 3.11 · Streamlit · Supabase")
