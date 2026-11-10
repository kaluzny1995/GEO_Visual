"""Tests for the United States phenomenon map."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import us_map

PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "9_United_States_Map.py"


def raw_map_frame() -> pd.DataFrame:
    """A small raw frame shaped like the map SQL result."""
    return pd.DataFrame(
        {
            "event_category": ["Avalanche", "Avalanche", "Fire", "Fire", "Volcano"],
            "event_subcategory": ["Avalanche", "Avalanche", "Wildfire", "Wildfire", "Volcano"],
            "event_title": ["Avalanche zone A", "Avalanche zone B", "Fire A", "Fire B", "Volcano A"],
            "latitude": [39.0, 40.0, 34.0, 35.0, 19.42],
            "longitude": [-106.0, -111.0, -118.0, -119.0, -155.29],
            "state_province": ["CO", "UT", "CA", "CA", "HI"],
            "place_location": ["Zone A", "Zone B", "Forest A", "Forest B", "Kilauea"],
            "danger_rating": ["low", "no_rating", "no_rating", "no_rating", "low"],
            "metric_name": ["size", "size", "area", "area", "vei"],
            "metric_value": [2.0, None, 10.0, 30.0, 4.0],
            "metric_unit": ["destructive size class", None, "km²", "km²", "VEI"],
            "other_metrics": [None, None, "contained: 50 %", None, "alert: watch"],
            "event_start_date": pd.to_datetime(["2026-11-01", "2026-11-01", "2026-11-02", "2026-11-02", "2026-11-03"]),
            "event_end_date": [pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT],
        }
    )


def load_frame() -> pd.DataFrame:
    """Load the raw frame through the real map preparation."""
    with patch.object(us_map, "cached_query", return_value=raw_map_frame()):
        return us_map.load_map_data(us_map.DEFAULT_MIN_MAGNITUDE)


class TestLoadMapData:
    """Tests for :func:`us_map.load_map_data`."""

    def test_forwards_the_threshold_and_normalises_intensity(self) -> None:
        """The query is parameterised and each phenomenon is scaled to 0-1."""
        with patch.object(us_map, "cached_query", return_value=raw_map_frame()) as query:
            frame = us_map.load_map_data(2.5)

        query.assert_called_once_with(
            us_map.MAP_QUERY,
            (("min_magnitude", 2.5),),
            max_rows=us_map.MAP_MAX_ROWS,
        )
        fire = frame[frame["event_category"] == "Fire"].sort_values("metric_value")
        assert fire["intensity"].tolist() == [0.0, 1.0]
        assert fire["text_size"].tolist() == [8.0, 18.0]
        assert pd.isna(frame[frame["metric_value"].isna()]["intensity"]).all()

    def test_builds_emoji_hover_text_with_the_main_metric(self) -> None:
        """Hover text identifies the phenomenon and its metric."""
        frame = load_frame()
        hover = frame[frame["event_title"] == "Fire A"]["hover_text"].iloc[0]

        assert "🔥 Fire A" in hover
        assert "area = 10" in hover
        assert "Danger rating: no_rating" in hover


class TestBuildMapFigure:
    """Tests for :func:`us_map.build_map_figure`."""

    def test_builds_one_trace_per_phenomenon_with_emoji_text_and_size_scale(self) -> None:
        """The map uses emoji text markers and a marker-size legend."""
        figure = us_map.build_map_figure(load_frame())

        names = [trace.name for trace in figure.data]
        assert "❄️ Avalanche" in names
        assert "🔥 Fire" in names
        assert "🌋 Volcano" in names
        assert figure.data[0].mode == "text"
        assert figure.data[0].text[0] == "❄️"
        assert figure.data[0].textfont.size[0] == 13.0
        assert figure.layout.title.text == "Phenomenon locations"
        assert figure.layout.geo.scope == "usa"
        annotations = [annotation.text for annotation in figure.layout.annotations]
        assert "Marker size" in annotations
        assert "Low" in annotations
        assert "High" in annotations

    def test_marks_points_without_a_main_metric_smaller(self) -> None:
        """Unrated avalanche zones stay visible at the smallest emoji size."""
        figure = us_map.build_map_figure(load_frame())
        grey = [trace for trace in figure.data if trace.name == "❄️ Avalanche (no main metric)"]

        assert len(grey) == 1
        assert grey[0].mode == "text"
        assert grey[0].textfont.size == 6
        assert grey[0].opacity == 0.35
        assert grey[0].showlegend is False

    def test_empty_frame_gets_an_annotation(self) -> None:
        """An empty filtered map explains why it has no points."""
        figure = us_map.build_map_figure(pd.DataFrame())

        assert not figure.data
        assert any("No phenomena" in annotation.text for annotation in figure.layout.annotations)


def run_page() -> AppTest:
    """Render the map page with the database replaced by sample data."""
    with patch.object(us_map, "cached_query", return_value=raw_map_frame()):
        return AppTest.from_file(str(PAGE_PATH), default_timeout=60).run()


def test_page_renders_the_map_and_controls() -> None:
    """The page renders the map, phenomenon selector and earthquake threshold."""
    at = run_page()

    assert not at.exception
    assert at.main.title[0].value == f"{us_map.PAGE_ICON} {us_map.PAGE_TITLE}"
    assert len(at.get("plotly_chart")) == 1
    assert [control.label for control in at.main.multiselect] == ["Phenomena"]
    assert [control.label for control in at.main.slider] == ["Minimum earthquake magnitude"]
    assert any("Marker size shows" in caption.value for caption in at.caption)


def test_page_empty_filter_state() -> None:
    """Removing every phenomenon leaves a friendly empty state."""
    at = run_page()
    at.main.multiselect[0].set_value([]).run()

    assert not at.exception
    assert any("Select at least one phenomenon" in info.value for info in at.main.info)
