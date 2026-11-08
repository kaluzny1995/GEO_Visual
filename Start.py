"""GEO_Visual — Streamlit entry point and welcome page."""

import streamlit as st

from utils.layout import CONFIG, configure_page, render_sidebar

configure_page()
render_sidebar()

st.title(f"{CONFIG.app.page_icon} {CONFIG.app.title}")
st.markdown(CONFIG.app.subtitle)

st.divider()
st.subheader("Dashboards")

with st.container(border=True):
    st.markdown("#### ❄️ Avalanche metrics timeline")
    st.markdown(
        "Daily snapshots from `geo.metrics_avalanche_vw`: avalanche danger levels, "
        "destructive size and any other numeric metric published by GEO_ETL. "
        "Each metric gets its own linear timeline, with a selectable date range and "
        "mean, maximum, total or observation-count statistic. Periods without "
        "observations are shaded and labelled, and `danger_level = -1` (no rating) "
        "is shown as recorded."
    )
    st.page_link(
        "pages/1_Avalanche_Timeline.py",
        label="Open Avalanche metrics timeline",
        icon="❄️",
    )
