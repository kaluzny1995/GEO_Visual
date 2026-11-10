"""GEO_Visual — Streamlit entry point and welcome page."""

import streamlit as st

from dashboard.catalog import DASHBOARDS, MAPS, DashboardCard
from utils.layout import CONFIG, configure_page, render_sidebar

configure_page()
render_sidebar()


def _render_cards(cards: tuple[DashboardCard, ...]) -> None:
    """Render one collapsible card per dashboard or map page."""
    for card in cards:
        with st.expander(f"{card.icon} {card.title}", expanded=False):
            st.markdown(card.description)
            st.page_link(
                card.page_path,
                label=f"Open {card.title}",
                icon=card.icon,
            )


st.title(f"{CONFIG.app.page_icon} {CONFIG.app.title}")
st.markdown(CONFIG.app.subtitle)

st.divider()
st.subheader("Dashboards")
_render_cards(DASHBOARDS)

st.subheader("Phenomenon maps")
_render_cards(MAPS)
