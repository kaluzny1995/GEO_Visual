"""GEO_Visual — Streamlit entry point and welcome page."""

import streamlit as st

from model.config.app_config import AppConfig
from utils.database import cached_connection_status, clear_connection_cache

CONFIG = AppConfig.from_json()

st.set_page_config(
    page_title=CONFIG.app.title,
    page_icon=CONFIG.app.page_icon,
    layout=CONFIG.app.layout,
    initial_sidebar_state="expanded",
)


def _render_sidebar() -> None:
    """Render branding, database status and pipeline links."""
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

        st.subheader("Pipeline")
        st.markdown(
            "- **GEO_Download** — raw data collection\n"
            "- **GEO_ETL** — Spark transformations\n"
            "- **GEO_API** — REST access\n"
            "- **GEO_E2E** — orchestration"
        )
        st.divider()
        st.caption("Python 3.11 · Streamlit · Supabase")


def _render_feature_cards() -> None:
    """Render the three planned dashboard areas."""
    cards = [
        (
            "🗂️",
            "Explore datasets",
            "Browse the analysis-ready tables GEO_ETL publishes to the `geo` schema.",
        ),
        (
            "🗺️",
            "Visualize geography",
            "Map events, sources and regional patterns with Plotly and Streamlit.",
        ),
        (
            "📈",
            "Monitor quality",
            "Track completeness, duplicates and field variation from `geo.data_quality`.",
        ),
    ]

    columns = st.columns(3)
    for column, (icon, title, description) in zip(columns, cards, strict=True):
        with column, st.container(border=True):
            st.subheader(f"{icon} {title}")
            st.write(description)
            st.caption("Coming soon")


def main() -> None:
    """Render the welcome page."""
    _render_sidebar()

    st.title(f"{CONFIG.app.page_icon} {CONFIG.app.title}")
    st.markdown(f"**{CONFIG.app.subtitle}**")
    st.caption("Python 3.11 · Streamlit · Supabase")
    st.divider()

    st.subheader("Welcome")
    st.write(
        "GEO_Visual is the presentation layer of the GEO geographic-data pipeline. "
        "It reads the clean datasets that GEO_ETL loads into Supabase and turns them "
        "into interactive Streamlit dashboards."
    )

    st.subheader("What you can do")
    _render_feature_cards()

    st.subheader("How it fits together")
    st.markdown(
        "1. **GEO_Download** fetches raw geospatial data into dated CSV files.\n"
        "2. **GEO_ETL** cleans, enriches and loads the data into Supabase.\n"
        "3. **GEO_API** serves the same data over a REST interface.\n"
        "4. **GEO_Visual** turns it into charts, maps and quality summaries."
    )

    st.subheader("Performance by design")
    st.markdown(
        "- **Direct Postgres access** — one hop from Streamlit to Supabase, with no API serialization.\n"
        "- **SQL pushdown** — aggregation and filtering run in the database; only chart-sized results "
        "cross the network.\n"
        "- **Guarded queries** — a row cap and statement timeout on every query, plus a bounded "
        "Streamlit cache.\n"
        "- **Read-only role recommended** — the dashboard only needs `SELECT` on the `geo` schema."
    )

    st.subheader("Quick start")
    st.code(
        "conda env create -f environment.yml\n"
        "conda activate geo_visual_311\n"
        "cp .env.example .env  # fill in the SUPABASE_DB_* values\n"
        "streamlit run app.py",
        language="bash",
    )
    st.info(
        "The welcome page works without a database. Add Supabase credentials to `.env` "
        "and use **Recheck connection** in the sidebar to verify the connection."
    )

    st.divider()
    st.caption("GEO_Visual is part of the GeographicData pipeline. See README.md for setup and development.")


main()
