"""Tests for the area phenomenon map dashboards."""

import datetime as dt
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard import phenomenon_map
from dashboard.catalog import MAPS
from dashboard.map_configs import MAP_CONFIGS, MAP_CONFIGS_BY_KEY, MapConfig

START_DATE = dt.date(2026, 11, 1)
END_DATE = dt.date(2026, 11, 3)
US_CONFIG = MAP_CONFIGS_BY_KEY["us"]
AFRICA_CONFIG = MAP_CONFIGS_BY_KEY["africa"]
WATERS_CONFIG = MAP_CONFIGS_BY_KEY["waters"]


def raw_map_frame() -> pd.DataFrame:
    """A small raw frame shaped like the area map SQL result."""
    return pd.DataFrame(
        {
            "event_category": ["Avalanche", "Avalanche", "Fire", "Fire", "Volcano", "Iceberg"],
            "event_subcategory": ["Avalanche", "Avalanche", "Wildfire", "Wildfire", "Volcano", "Iceberg"],
            "event_title": ["Avalanche zone A", "Avalanche zone B", "Fire A", "Fire B", "Volcano A", "Iceberg A"],
            "latitude": [39.0, 40.0, 34.0, 35.0, 19.42, -72.69],
            "longitude": [-106.0, -111.0, -118.0, -119.0, -155.29, -75.80],
            "country_code": ["US", "US", "CA", "CA", "US", "AQ"],
            "state_province": ["CO", "UT", "CA", "CA", "HI", None],
            "place_location": ["Zone A", "Zone B", "Forest A", "Forest B", "Kilauea", "Southern Ocean"],
            "danger_rating": ["low", "no_rating", "no_rating", "no_rating", "low", "no_rating"],
            "metric_name": ["size", "size", "area", "area", "vei", "surface"],
            "metric_value": [2.0, None, 10.0, 30.0, 4.0, 30.0],
            "metric_unit": ["destructive size class", None, "km²", "km²", "VEI", "N/m²"],
            "other_metrics": [None, None, "contained: 50 %", None, "alert: watch", None],
            "event_start_date": pd.to_datetime(
                ["2026-11-01", "2026-11-01", "2026-11-02", "2026-11-02", "2026-11-03", "2026-11-03"]
            ),
            "event_end_date": [pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT],
        }
    )


def single_earthquake_frame() -> pd.DataFrame:
    """A minimal raw frame with one earthquake."""
    return pd.DataFrame(
        {
            "event_category": ["Earthquake"],
            "event_subcategory": ["Earthquake"],
            "event_title": ["Earthquake A"],
            "latitude": [35.0],
            "longitude": [-120.0],
            "country_code": ["US"],
            "state_province": ["CA"],
            "place_location": ["Near A"],
            "danger_rating": ["no_rating"],
            "metric_name": ["magnitude"],
            "metric_value": [4.0],
            "metric_unit": ["Mw"],
            "other_metrics": [None],
            "event_start_date": pd.to_datetime(["2026-11-02"]),
            "event_end_date": [pd.NaT],
        }
    )


def raw_metadata_frame() -> pd.DataFrame:
    """A small raw frame shaped like the metadata SQL result."""
    return pd.DataFrame(
        {
            "min_date": ["2026-11-01"],
            "max_date": ["2026-11-03"],
            "categories": [["Volcano", "Fire", "Unknown", "Avalanche"]],
        }
    )


def load_frame(config: MapConfig = US_CONFIG) -> pd.DataFrame:
    """Load the raw frame through the real map preparation."""
    with patch.object(phenomenon_map, "cached_query", return_value=raw_map_frame()):
        return phenomenon_map.load_map_data(config, phenomenon_map.DEFAULT_MIN_MAGNITUDE, START_DATE, END_DATE)


class TestMapConfigs:
    """Tests for the area map configuration metadata."""

    def test_every_view_has_one_config_and_catalog_card(self) -> None:
        """All nine area views are represented consistently on the overview."""
        cards = {card.page_path: card for card in MAPS}

        assert len(MAP_CONFIGS) == 9
        assert len({config.key for config in MAP_CONFIGS}) == len(MAP_CONFIGS)
        assert len({config.page_path for config in MAP_CONFIGS}) == len(MAP_CONFIGS)
        assert all(config.view_name.startswith("geo.phenomenons_") for config in MAP_CONFIGS)
        for config in MAP_CONFIGS:
            card = cards[config.page_path]
            assert card.nav_label == config.nav_label
            assert card.title == config.title
            assert card.icon == config.icon
            assert card.description == config.description

    def test_united_states_titles_and_description(self) -> None:
        """The US map keeps the requested locations heading."""
        assert US_CONFIG.locations_title == "Phenomenon locations for United States"
        assert US_CONFIG.title == "United States phenomenon map"
        assert "geo.phenomenons_us_vw" in US_CONFIG.description


class TestLoadMapMetadata:
    """Tests for :func:`phenomenon_map.load_map_metadata`."""

    def test_loads_dates_and_orders_categories(self) -> None:
        """The metadata query is view-specific and categories follow the shared order."""
        with patch.object(phenomenon_map, "cached_query", return_value=raw_metadata_frame()) as query:
            metadata = phenomenon_map.load_map_metadata(US_CONFIG)

        sent_query = query.call_args.args[0]
        assert "geo.phenomenons_us_vw" in sent_query
        assert "{view_name}" not in sent_query
        assert metadata == phenomenon_map.MapMetadata(
            min_date=START_DATE,
            max_date=END_DATE,
            categories=("Avalanche", "Fire", "Volcano", "Unknown"),
        )

    def test_returns_none_for_an_empty_view(self) -> None:
        """An empty view leaves the page without a date range."""
        with patch.object(phenomenon_map, "cached_query", return_value=pd.DataFrame()):
            assert phenomenon_map.load_map_metadata(US_CONFIG) is None

    def test_returns_none_when_the_view_has_no_dated_events(self) -> None:
        """Missing dates or categories are treated as no data."""
        missing_dates = pd.DataFrame({"min_date": [None], "max_date": [None], "categories": [None]})
        with patch.object(phenomenon_map, "cached_query", return_value=missing_dates):
            assert phenomenon_map.load_map_metadata(US_CONFIG) is None

        missing_categories = pd.DataFrame({"min_date": ["2026-11-01"], "max_date": ["2026-11-03"], "categories": [[]]})
        with patch.object(phenomenon_map, "cached_query", return_value=missing_categories):
            assert phenomenon_map.load_map_metadata(US_CONFIG) is None


class TestLoadMapData:
    """Tests for :func:`phenomenon_map.load_map_data`."""

    def test_forwards_the_view_and_filters_and_normalises_intensity(self) -> None:
        """The query is view-specific and each phenomenon is scaled to 0-1."""
        with patch.object(phenomenon_map, "cached_query", return_value=raw_map_frame()) as query:
            frame = phenomenon_map.load_map_data(US_CONFIG, 2.5, START_DATE, END_DATE)

        sent_query = query.call_args.args[0]
        assert "geo.phenomenons_us_vw" in sent_query
        assert "{view_name}" not in sent_query
        query.assert_called_once_with(
            sent_query,
            (
                ("min_magnitude", 2.5),
                ("start_date", "2026-11-01"),
                ("end_date", "2026-11-03"),
            ),
            max_rows=phenomenon_map.MAP_MAX_ROWS,
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
        ranges = {category: (style.min_size, style.max_size) for category, style in phenomenon_map.PHENOMENA.items()}

        assert len(set(ranges.values())) == len(ranges)
        assert all(minimum < maximum for minimum, maximum in ranges.values())
        assert ranges["Earthquake"] == (6, 14)
        assert ranges["Iceberg"] == (13, 23)

    def test_size_legend_uses_emoji_sizes_and_actual_ranges(self) -> None:
        """The legend shows each phenomenon's values between correctly sized emojis."""
        legend = phenomenon_map._size_legend_html(load_frame())

        assert 'style="font-size:9px">🔥' in legend
        assert 'style="font-size:18px">🔥' in legend
        assert 'style="font-size:13px">🧊' in legend
        assert 'style="font-size:23px">🧊' in legend
        assert "10" in legend
        assert "30" in legend
        assert "surface · N/m²" in legend
        assert "●" not in legend

    def test_summary_cards_use_the_configured_region_field(self) -> None:
        """US cards use states, other areas use countries and waters use areas."""
        frame = load_frame()
        us_cards = phenomenon_map._summary_cards_html(frame, US_CONFIG)
        africa_cards = phenomenon_map._summary_cards_html(frame, AFRICA_CONFIG)
        waters_cards = phenomenon_map._summary_cards_html(frame, WATERS_CONFIG)

        assert '<div class="area-map-card-count">2</div>' in us_cards
        assert "Mean area" in us_cards
        assert "20 km²" in us_cards
        assert "Top state" in us_cards
        assert "CA · 2" in us_cards
        assert "Top country" in africa_cards
        assert "Top area" in waters_cards
        assert "Southern Ocean · 1" in waters_cards

    def test_summary_and_size_legend_are_empty_for_no_data(self) -> None:
        """No cards or legend items are rendered without map data."""
        empty = pd.DataFrame()

        assert phenomenon_map._summary_cards_html(empty, US_CONFIG) == ""
        assert phenomenon_map._size_legend_html(empty) == ""


class TestBuildMapFigure:
    """Tests for :func:`phenomenon_map.build_map_figure`."""

    def test_builds_one_trace_per_phenomenon_with_emoji_text_and_a_frame(self) -> None:
        """The map uses emoji text markers and a visible rectangle frame."""
        figure = phenomenon_map.build_map_figure(load_frame(), US_CONFIG)

        names = [trace.name for trace in figure.data]
        assert "❄️ Avalanche" in names
        assert "🔥 Fire" in names
        assert "🧊 Iceberg" in names
        assert figure.data[0].mode == "text"
        assert figure.data[0].text[0] == "❄️"
        assert figure.data[0].textfont.size[0] == 15.0
        assert figure.layout.title.text is None
        assert figure.layout.geo.scope == "usa"
        shapes = list(figure.layout.shapes)
        assert len(shapes) == 1
        assert shapes[0].type == "rect"
        assert shapes[0].line.color == "#64748b"

    def test_applies_area_projection_and_zoom_settings(self) -> None:
        """Different areas use their configured projection and viewport."""
        canada = phenomenon_map.build_map_figure(load_frame(), MAP_CONFIGS_BY_KEY["ca"])
        russia = phenomenon_map.build_map_figure(load_frame(), MAP_CONFIGS_BY_KEY["ru"])

        assert canada.layout.geo.scope == "north america"
        assert tuple(canada.layout.geo.lonaxis.range) == (-141.0, -52.0)
        assert tuple(canada.layout.geo.lataxis.range) == (41.0, 84.0)
        assert russia.layout.geo.projection.type == "orthographic"
        assert russia.layout.geo.projection.rotation.lon == 100.0
        assert russia.layout.geo.projection.rotation.lat == 60.0

    def test_wraps_longitudes_for_dateline_projections(self) -> None:
        """Australia & Oceania points east of the dateline stay on one map."""
        part = pd.DataFrame({"longitude": [-179.0, 150.0]})
        wrapped = phenomenon_map._plot_longitudes(part, MAP_CONFIGS_BY_KEY["aus_oc"])

        assert wrapped.tolist() == [181.0, 150.0]

    def test_marks_points_without_a_main_metric_smaller(self) -> None:
        """Unrated avalanche zones stay visible at the smallest emoji size."""
        figure = phenomenon_map.build_map_figure(load_frame(), US_CONFIG)
        unrated = [trace for trace in figure.data if trace.name == "❄️ Avalanche (no main metric)"]

        assert len(unrated) == 1
        assert unrated[0].mode == "text"
        assert unrated[0].textfont.size == 10
        assert unrated[0].opacity == 0.35
        assert unrated[0].showlegend is False

    def test_empty_frame_gets_an_annotation(self) -> None:
        """An empty filtered map explains why it has no points."""
        figure = phenomenon_map.build_map_figure(pd.DataFrame(), US_CONFIG)

        assert not figure.data
        assert any("No phenomena" in annotation.text for annotation in figure.layout.annotations)


@contextmanager
def page_patches(config: MapConfig, raw_frame: pd.DataFrame, categories: tuple[str, ...]) -> Iterator[None]:
    """Replace the map queries with deterministic sample data."""
    metadata = phenomenon_map.MapMetadata(min_date=START_DATE, max_date=END_DATE, categories=categories)
    with (
        patch.object(phenomenon_map, "load_map_metadata", return_value=metadata),
        patch.object(phenomenon_map, "cached_query", return_value=raw_frame),
    ):
        yield


def run_page(config: MapConfig) -> AppTest:
    """Render one map page with the database replaced by sample data."""
    with page_patches(config, raw_map_frame(), ("Fire",)):
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / config.page_path), default_timeout=60).run()


@pytest.mark.parametrize("config", MAP_CONFIGS, ids=lambda config: config.key)
class TestEveryMapPage:
    """Parametrized page tests for all area dashboards."""

    def test_page_renders_filters_cards_legend_and_map(self, config: MapConfig) -> None:
        """Every map page has its title, heading, filters, cards and map."""
        at = run_page(config)

        assert not at.exception
        assert at.main.title[0].value == f"{config.icon} {config.title}"
        assert at.main.subheader[0].value == config.locations_title
        assert config.description in [markdown.value for markdown in at.main.markdown]
        assert [control.label for control in at.main.date_input] == ["Event date range"]
        assert at.main.date_input[0].value == (START_DATE, END_DATE)
        assert [control.label for control in at.main.multiselect] == ["Phenomena"]
        assert at.main.multiselect[0].value == ["Fire"]
        assert len(at.get("plotly_chart")) == 1
        markdown_values = [markdown.value for markdown in at.main.markdown]
        assert any("area-map-cards" in value for value in markdown_values)
        assert any("area-map-size-legend" in value for value in markdown_values)
        assert not at.main.dataframe
        assert any("Marker size shows" in caption.value for caption in at.caption)

    def test_page_reports_missing_metadata(self, config: MapConfig) -> None:
        """A view without dated events gets a friendly empty state."""
        with patch.object(phenomenon_map, "load_map_metadata", return_value=None):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / config.page_path), default_timeout=60
            ).run()

        assert not at.exception
        assert any(f"{config.view_name} yet" in info.value for info in at.main.info)


class TestUnitedStatesPage:
    """Additional interaction tests on the US map page."""

    def test_page_shows_the_earthquake_threshold(self) -> None:
        """Earthquake maps expose the magnitude slider."""
        with page_patches(US_CONFIG, single_earthquake_frame(), ("Earthquake",)):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / US_CONFIG.page_path), default_timeout=60
            ).run()

        assert not at.exception
        assert [control.label for control in at.main.slider] == ["Minimum earthquake magnitude"]
        assert at.main.slider[0].value == phenomenon_map.DEFAULT_MIN_MAGNITUDE

    def test_page_passes_the_selected_date_range_to_the_map_query(self) -> None:
        """Changing the date picker forwards the chosen range to the map query."""
        prepared = load_frame()
        metadata = phenomenon_map.MapMetadata(min_date=START_DATE, max_date=END_DATE, categories=("Fire",))
        with (
            patch.object(phenomenon_map, "load_map_metadata", return_value=metadata),
            patch.object(phenomenon_map, "load_map_data", return_value=prepared) as load,
        ):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / US_CONFIG.page_path), default_timeout=60
            ).run()
            selected = dt.date(2026, 11, 2)
            at.main.date_input[0].set_value((selected, selected)).run()

        assert not at.exception
        load.assert_called_with(US_CONFIG, phenomenon_map.DEFAULT_MIN_MAGNITUDE, selected, selected)

    def test_page_empty_filter_state(self) -> None:
        """Removing every phenomenon leaves a friendly empty state."""
        with page_patches(US_CONFIG, raw_map_frame(), ("Fire",)):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / US_CONFIG.page_path), default_timeout=60
            ).run()
            at.main.multiselect[0].set_value([]).run()

        assert not at.exception
        assert any("Select at least one phenomenon" in info.value for info in at.main.info)
