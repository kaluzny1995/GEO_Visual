"""Tests for the United States phenomenon map."""

import datetime as dt
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import us_map
from dashboard.catalog import MAPS

PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "9_United_States_Map.py"
START_DATE = dt.date(2026, 11, 1)
END_DATE = dt.date(2026, 11, 3)


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


def raw_date_bounds_frame() -> pd.DataFrame:
    """A small raw frame shaped like the date-bounds SQL result."""
    return pd.DataFrame({"min_date": ["2026-11-01"], "max_date": ["2026-11-03"]})


def load_frame() -> pd.DataFrame:
    """Load the raw frame through the real map preparation."""
    with patch.object(us_map, "cached_query", return_value=raw_map_frame()):
        return us_map.load_map_data(us_map.DEFAULT_MIN_MAGNITUDE, START_DATE, END_DATE)


class TestLoadMapDateBounds:
    """Tests for :func:`us_map.load_map_date_bounds`."""

    def test_loads_the_first_and_last_event_dates(self) -> None:
        """The date picker bounds come from the dedicated SQL script."""
        with patch.object(us_map, "cached_query", return_value=raw_date_bounds_frame()) as query:
            bounds = us_map.load_map_date_bounds()

        query.assert_called_once_with(us_map.MAP_DATE_BOUNDS_QUERY)
        assert bounds == (START_DATE, END_DATE)

    def test_returns_none_for_an_empty_view(self) -> None:
        """An empty view leaves the page without a date range."""
        with patch.object(us_map, "cached_query", return_value=pd.DataFrame()):
            assert us_map.load_map_date_bounds() is None

    def test_returns_none_when_the_view_has_no_dated_events(self) -> None:
        """Missing minimum or maximum dates are treated as no data."""
        frame = pd.DataFrame({"min_date": [None], "max_date": [None]})
        with patch.object(us_map, "cached_query", return_value=frame):
            assert us_map.load_map_date_bounds() is None


class TestLoadMapData:
    """Tests for :func:`us_map.load_map_data`."""

    def test_forwards_the_filters_and_normalises_intensity(self) -> None:
        """The query is parameterised and each phenomenon is scaled to 0-1."""
        with patch.object(us_map, "cached_query", return_value=raw_map_frame()) as query:
            frame = us_map.load_map_data(2.5, START_DATE, END_DATE)

        query.assert_called_once_with(
            us_map.MAP_QUERY,
            (
                ("min_magnitude", 2.5),
                ("start_date", "2026-11-01"),
                ("end_date", "2026-11-03"),
            ),
            max_rows=us_map.MAP_MAX_ROWS,
        )
        fire = frame[frame["event_category"] == "Fire"].sort_values("metric_value")
        assert fire["intensity"].tolist() == [0.0, 1.0]
        assert fire["text_size"].tolist() == [9.0, 18.0]
        assert pd.isna(frame[frame["metric_value"].isna()]["intensity"]).all()

    def test_missing_main_metric_uses_the_phenomenon_minimum_size(self) -> None:
        """Unrated avalanche points use avalanche's own minimum emoji size."""
        frame = load_frame()
        unrated = frame[frame["event_title"] == "Avalanche zone B"]

        assert unrated["text_size"].tolist() == [10.0]

    def test_builds_emoji_hover_text_with_the_main_metric(self) -> None:
        """Hover text identifies the phenomenon and its metric."""
        frame = load_frame()
        hover = frame[frame["event_title"] == "Fire A"]["hover_text"].iloc[0]

        assert "🔥 Fire A" in hover
        assert "area = 10" in hover
        assert "Danger rating: no_rating" in hover


class TestMapStyles:
    """Tests for per-phenomenon marker sizes and the legend content."""

    def test_marker_size_ranges_are_configured_per_phenomenon(self) -> None:
        """Every phenomenon has its own explicit emoji size range."""
        ranges = {category: (style.min_size, style.max_size) for category, style in us_map.PHENOMENA.items()}

        assert len(set(ranges.values())) == len(ranges)
        assert all(minimum < maximum for minimum, maximum in ranges.values())
        assert ranges["Earthquake"] == (6, 14)

    def test_size_legend_uses_emoji_sizes_and_actual_ranges(self) -> None:
        """The legend shows each phenomenon's values between correctly sized emojis."""
        legend = us_map._size_legend_html(load_frame())

        assert 'style="font-size:9px">🔥' in legend
        assert 'style="font-size:18px">🔥' in legend
        assert "10" in legend
        assert "30" in legend
        assert "area · km²" in legend
        assert "●" not in legend

    def test_summary_cards_report_count_mean_and_top_region(self) -> None:
        """Each card summarises the POIs, mean metric and top region."""
        cards = us_map._summary_cards_html(load_frame())

        assert "🔥" in cards
        assert "Fire" in cards
        assert '<div class="us-map-card-count">2</div>' in cards
        assert "Mean area" in cards
        assert "20 km²" in cards
        assert "CA · 2" in cards
        assert "Avalanche" in cards
        assert "2 destructive size class" in cards

    def test_summary_and_size_legend_are_empty_for_no_data(self) -> None:
        """No cards or legend items are rendered without map data."""
        empty = pd.DataFrame()

        assert us_map._summary_cards_html(empty) == ""
        assert us_map._size_legend_html(empty) == ""


class TestBuildMapFigure:
    """Tests for :func:`us_map.build_map_figure`."""

    def test_builds_one_trace_per_phenomenon_with_emoji_text_and_a_frame(self) -> None:
        """The map uses emoji text markers and a visible rectangle frame."""
        figure = us_map.build_map_figure(load_frame())

        names = [trace.name for trace in figure.data]
        assert "❄️ Avalanche" in names
        assert "🔥 Fire" in names
        assert "🌋 Volcano" in names
        assert figure.data[0].mode == "text"
        assert figure.data[0].text[0] == "❄️"
        assert figure.data[0].textfont.size[0] == 15.0
        assert figure.layout.title.text == "Phenomenon locations"
        assert figure.layout.geo.scope == "usa"
        shapes = list(figure.layout.shapes)
        assert len(shapes) == 1
        assert shapes[0].type == "rect"
        assert shapes[0].line.color == "#64748b"
        annotations = [annotation.text for annotation in figure.layout.annotations]
        assert not any("Marker size" in text for text in annotations)

    def test_marks_points_without_a_main_metric_smaller(self) -> None:
        """Unrated avalanche zones stay visible at the smallest emoji size."""
        figure = us_map.build_map_figure(load_frame())
        unrated = [trace for trace in figure.data if trace.name == "❄️ Avalanche (no main metric)"]

        assert len(unrated) == 1
        assert unrated[0].mode == "text"
        assert unrated[0].textfont.size == 10
        assert unrated[0].opacity == 0.35
        assert unrated[0].showlegend is False

    def test_empty_frame_gets_an_annotation(self) -> None:
        """An empty filtered map explains why it has no points."""
        figure = us_map.build_map_figure(pd.DataFrame())

        assert not figure.data
        assert any("No phenomena" in annotation.text for annotation in figure.layout.annotations)


@contextmanager
def map_data_patches() -> Iterator[None]:
    """Replace the map queries with deterministic sample data."""
    with (
        patch.object(us_map, "load_map_date_bounds", return_value=(START_DATE, END_DATE)),
        patch.object(us_map, "cached_query", return_value=raw_map_frame()),
    ):
        yield


class TestPage:
    """Tests for the Streamlit map page."""

    @staticmethod
    def run_page() -> AppTest:
        """Render the map page with the database replaced by sample data."""
        with map_data_patches():
            return AppTest.from_file(str(PAGE_PATH), default_timeout=60).run()

    def test_page_icon_is_the_us_flag(self) -> None:
        """The page and catalog card use the United States flag."""
        assert us_map.PAGE_ICON == "🇺🇸"
        assert MAPS[0].icon == us_map.PAGE_ICON

    def test_page_renders_filters_cards_legend_and_map(self) -> None:
        """The page renders the date filter, summary cards, legend and map."""
        at = self.run_page()

        assert not at.exception
        assert at.main.title[0].value == f"{us_map.PAGE_ICON} {us_map.PAGE_TITLE}"
        assert [control.label for control in at.main.date_input] == ["Event date range"]
        assert at.main.date_input[0].value == (START_DATE, END_DATE)
        assert [control.label for control in at.main.multiselect] == ["Phenomena"]
        assert [control.label for control in at.main.slider] == ["Minimum earthquake magnitude"]
        assert len(at.get("plotly_chart")) == 1
        markdown_values = [markdown.value for markdown in at.main.markdown]
        assert any("us-map-cards" in value for value in markdown_values)
        assert any("us-map-size-legend" in value for value in markdown_values)
        assert not at.main.dataframe
        assert any("Marker size shows" in caption.value for caption in at.caption)

    def test_page_passes_the_selected_date_range_to_the_map_query(self) -> None:
        """Changing the date picker forwards the chosen range to the map query."""
        prepared = load_frame()
        with (
            patch.object(us_map, "load_map_date_bounds", return_value=(START_DATE, END_DATE)),
            patch.object(us_map, "load_map_data", return_value=prepared) as load,
        ):
            at = AppTest.from_file(str(PAGE_PATH), default_timeout=60).run()
            selected = dt.date(2026, 11, 2)
            at.main.date_input[0].set_value((selected, selected)).run()

        assert not at.exception
        load.assert_called_with(us_map.DEFAULT_MIN_MAGNITUDE, selected, selected)

    def test_page_reports_missing_date_bounds(self) -> None:
        """A view without dated events gets a friendly empty state."""
        with patch.object(us_map, "load_map_date_bounds", return_value=None):
            at = AppTest.from_file(str(PAGE_PATH), default_timeout=60).run()

        assert not at.exception
        assert any("No phenomena are available" in info.value for info in at.main.info)

    def test_page_empty_filter_state(self) -> None:
        """Removing every phenomenon leaves a friendly empty state."""
        with map_data_patches():
            at = AppTest.from_file(str(PAGE_PATH), default_timeout=60).run()
            at.main.multiselect[0].set_value([]).run()

        assert not at.exception
        assert any("Select at least one phenomenon" in info.value for info in at.main.info)
