"""Area configurations for the natural-phenomenon map dashboards."""

from dataclasses import dataclass
from typing import Final, Literal

RegionField = Literal["country_code", "state_province", "place_location"]


@dataclass(frozen=True)
class MapConfig:
    """Metadata and geographic settings for one area map.

    Attributes:
        key: Area key used in the view name and SQL template.
        page_path: Streamlit page file, relative to the project root.
        nav_label: Short label used in the sidebar and welcome card.
        title: Full dashboard title used in the page header.
        locations_title: Heading shown above the map filter controls.
        icon: Emoji shared by the card, page, sidebar and browser tab.
        scope: Plotly geo scope.
        projection: Plotly geo projection type.
        region_field: Column used for the top-region summary card.
        region_label: Label for the top-region card row.
        fallback_region: Region label used when the configured column is empty.
        location_phrase: Natural-language place phrase used in the description.
        lon_range: Optional Plotly longitude axis range.
        lat_range: Optional Plotly latitude axis range.
        wrap_longitude: Whether negative longitudes should be shifted by 360°.
        rotation: Optional ``(longitude, latitude)`` projection centre.
    """

    key: str
    page_path: str
    nav_label: str
    title: str
    locations_title: str
    icon: str
    scope: str
    projection: str
    region_field: RegionField
    region_label: str
    fallback_region: str
    location_phrase: str
    lon_range: tuple[float, float] | None = None
    lat_range: tuple[float, float] | None = None
    wrap_longitude: bool = False
    rotation: tuple[float, float] | None = None

    @property
    def view_name(self) -> str:
        """The GEO view queried by this map."""
        return f"geo.phenomenons_{self.key}_vw"

    @property
    def description(self) -> str:
        """Welcome-card and page description."""
        return (
            f"Interactive map of natural-phenomenon locations {self.location_phrase} "
            f"from `{self.view_name}`. Filter by event date range and phenomenon, "
            "review per-phenomenon summary cards, and use the emoji markers whose size "
            "shows the main metric; hover reveals the event, location, metric value, "
            "danger rating and dates."
        )


MAP_CONFIGS: Final[tuple[MapConfig, ...]] = (
    MapConfig(
        key="us",
        page_path="pages/9_United_States_Map.py",
        nav_label="United States",
        title="United States phenomenon map",
        locations_title="Phenomenon locations for United States",
        icon="🇺🇸",
        scope="usa",
        projection="albers usa",
        region_field="state_province",
        region_label="Top state",
        fallback_region="United States",
        location_phrase="across the United States",
    ),
    MapConfig(
        key="ca",
        page_path="pages/10_Canada_Map.py",
        nav_label="Canada",
        title="Canada phenomenon map",
        locations_title="Phenomenon locations for Canada",
        icon="🇨🇦",
        scope="north america",
        projection="natural earth",
        region_field="state_province",
        region_label="Top province",
        fallback_region="Canada",
        location_phrase="across Canada",
        lon_range=(-141.0, -52.0),
        lat_range=(41.0, 84.0),
    ),
    MapConfig(
        key="cs_amer",
        page_path="pages/11_Central_South_America_Map.py",
        nav_label="Central & South America",
        title="Central & South America phenomenon map",
        locations_title="Phenomenon locations for Central & South America",
        icon="🌎",
        scope="south america",
        projection="natural earth",
        region_field="country_code",
        region_label="Top country",
        fallback_region="Central & South America",
        location_phrase="across Central & South America",
    ),
    MapConfig(
        key="europe",
        page_path="pages/12_Europe_Map.py",
        nav_label="Europe",
        title="Europe phenomenon map",
        locations_title="Phenomenon locations for Europe",
        icon="🇪🇺",
        scope="europe",
        projection="natural earth",
        region_field="country_code",
        region_label="Top country",
        fallback_region="Europe",
        location_phrase="across Europe",
    ),
    MapConfig(
        key="africa",
        page_path="pages/13_Africa_Map.py",
        nav_label="Africa",
        title="Africa phenomenon map",
        locations_title="Phenomenon locations for Africa",
        icon="🌍",
        scope="africa",
        projection="natural earth",
        region_field="country_code",
        region_label="Top country",
        fallback_region="Africa",
        location_phrase="across Africa",
    ),
    MapConfig(
        key="asia",
        page_path="pages/14_Asia_Map.py",
        nav_label="Asia",
        title="Asia phenomenon map",
        locations_title="Phenomenon locations for Asia",
        icon="🌏",
        scope="asia",
        projection="natural earth",
        region_field="country_code",
        region_label="Top country",
        fallback_region="Asia",
        location_phrase="across Asia",
    ),
    MapConfig(
        key="aus_oc",
        page_path="pages/15_Australia_Oceania_Map.py",
        nav_label="Australia & Oceania",
        title="Australia & Oceania phenomenon map",
        locations_title="Phenomenon locations for Australia & Oceania",
        icon="🇦🇺",
        scope="world",
        projection="equirectangular",
        region_field="country_code",
        region_label="Top country",
        fallback_region="Australia & Oceania",
        location_phrase="across Australia & Oceania",
        lon_range=(90.0, 210.0),
        lat_range=(-50.0, 35.0),
        wrap_longitude=True,
    ),
    MapConfig(
        key="ru",
        page_path="pages/16_Russia_Map.py",
        nav_label="Russia",
        title="Russia phenomenon map",
        locations_title="Phenomenon locations for Russia",
        icon="🇷🇺",
        scope="world",
        projection="orthographic",
        region_field="state_province",
        region_label="Top region",
        fallback_region="Russia",
        location_phrase="across Russia",
        rotation=(100.0, 60.0),
    ),
    MapConfig(
        key="waters",
        page_path="pages/17_International_Waters_Map.py",
        nav_label="International waters",
        title="International waters phenomenon map",
        locations_title="Phenomenon locations in international waters",
        icon="🌊",
        scope="world",
        projection="natural earth",
        region_field="place_location",
        region_label="Top area",
        fallback_region="International waters",
        location_phrase="in international waters",
    ),
)

MAP_CONFIGS_BY_KEY: Final[dict[str, MapConfig]] = {config.key: config for config in MAP_CONFIGS}
