"""GEO_Visual — Streamlit entry point and welcome page."""

import streamlit as st

from dashboard.catalog import DASHBOARDS
from utils.layout import CONFIG, configure_page, render_sidebar

configure_page()
render_sidebar()

st.title(f"{CONFIG.app.page_icon} {CONFIG.app.title}")
st.markdown(CONFIG.app.subtitle)

st.divider()
st.subheader("Dashboards")

for dashboard in DASHBOARDS:
    with st.container(border=True):
        st.markdown(f"#### {dashboard.icon} {dashboard.title}")
        st.markdown(dashboard.description)
        st.page_link(
            dashboard.page_path,
            label=f"Open {dashboard.title}",
            icon=dashboard.icon,
        )
