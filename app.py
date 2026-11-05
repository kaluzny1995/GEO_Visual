"""GEO_Visual — Streamlit entry point and welcome page."""

import streamlit as st

from model.config.app_config import AppConfig
from utils.database import cached_connection_status, clear_connection_cache

CONFIG = AppConfig.from_json()

st.set_page_config(
    page_title=CONFIG.app.title,
    page_icon=CONFIG.app.page_icon,
    layout=CONFIG.app.layout,
)


def _render_sidebar() -> None:
    """Render branding and the Supabase connection status."""
    with st.sidebar:
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


_render_sidebar()

st.title(f"{CONFIG.app.page_icon} {CONFIG.app.title}")
st.markdown(CONFIG.app.subtitle)
