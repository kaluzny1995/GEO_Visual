"""Dashboard metadata shared by the welcome page and the sidebar."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class DashboardCard:
    """One dashboard entry shown on the welcome page and in the sidebar.

    Attributes:
        page_path: Streamlit page file, relative to the project root.
        nav_label: Short label used in the sidebar.
        title: Full dashboard title used on the welcome card.
        icon: Emoji shared by the card, page and sidebar.
        description: Short welcome-page description.
    """

    page_path: str
    nav_label: str
    title: str
    icon: str
    description: str


def _description(prefix: str, extra: str = "") -> str:
    """Build the shared dashboard-card description.

    Args:
        prefix: Dashboard-specific opening sentence.
        extra: Optional dashboard-specific closing sentence.

    Returns:
        The complete welcome-card description.
    """
    return (
        f"{prefix} Each metric gets its own timeline and value distribution histogram, "
        "with a selectable date range and mean, median, maximum, total or "
        "observation-count statistic. Periods without observations are shaded and labelled."
        f"{extra}"
    )


DASHBOARDS: Final[tuple[DashboardCard, ...]] = (
    DashboardCard(
        page_path="pages/1_Avalanche_Timeline.py",
        nav_label="Avalanche",
        title="Avalanche metrics timeline & distribution",
        icon="❄️",
        description=_description(
            "Daily snapshots from `geo.metrics_avalanche_vw`: avalanche danger levels, "
            "destructive size and any other numeric metric published by GEO_ETL.",
            " `danger_level = -1` (no rating) is shown as recorded.",
        ),
    ),
    DashboardCard(
        page_path="pages/2_Drought_Timeline.py",
        nav_label="Drought",
        title="Drought metrics timeline & distribution",
        icon="🌵",
        description=_description(
            "Daily snapshots from `geo.metrics_drought_vw`: drought area and any other "
            "numeric metric published by GEO_ETL."
        ),
    ),
    DashboardCard(
        page_path="pages/3_Earthquake_Timeline.py",
        nav_label="Earthquake",
        title="Earthquake metrics timeline & distribution",
        icon="🏚️",
        description=_description(
            "Daily snapshots from `geo.metrics_earthquake_vw`: magnitude, depth, station "
            "counts and any other numeric metric published by GEO_ETL."
        ),
    ),
    DashboardCard(
        page_path="pages/4_Fire_Timeline.py",
        nav_label="Fire",
        title="Fire metrics timeline & distribution",
        icon="🔥",
        description=_description(
            "Daily snapshots from `geo.metrics_fire_vw`: burned area, percent contained "
            "and any other numeric fire metric published by GEO_ETL."
        ),
    ),
    DashboardCard(
        page_path="pages/5_Flood_Timeline.py",
        nav_label="Flood",
        title="Flood metrics timeline & distribution",
        icon="🌊",
        description=_description(
            "Daily snapshots from `geo.metrics_flood_vw`: discharge, threshold, "
            "exceedance ratio and any other numeric flood metric."
        ),
    ),
    DashboardCard(
        page_path="pages/6_Iceberg_Timeline.py",
        nav_label="Iceberg",
        title="Iceberg metrics timeline & distribution",
        icon="🧊",
        description=_description(
            "Daily snapshots from `geo.metrics_iceberg_vw`: surface area, geometry counts "
            "and any other numeric iceberg metric published by GEO_ETL."
        ),
    ),
    DashboardCard(
        page_path="pages/7_Storm_Timeline.py",
        nav_label="Storm",
        title="Storm metrics timeline & distribution",
        icon="⛈️",
        description=_description(
            "Daily snapshots from `geo.metrics_storm_vw`: wind speed, gusts, pressure, "
            "direction, landfall, distance to land, geometry counts and any other numeric "
            "storm metric."
        ),
    ),
    DashboardCard(
        page_path="pages/8_Volcano_Timeline.py",
        nav_label="Volcano",
        title="Volcano metrics timeline & distribution",
        icon="🌋",
        description=_description(
            "Daily snapshots from `geo.metrics_volcano_vw`: VEI, Smithsonian volcano "
            "number and any other numeric volcano metric."
        ),
    ),
)

MAPS: Final[tuple[DashboardCard, ...]] = (
    DashboardCard(
        page_path="pages/9_United_States_Map.py",
        nav_label="United States",
        title="United States phenomenon map",
        icon="🇺🇸",
        description=(
            "Interactive map of natural-phenomenon locations across the United States "
            "from `geo.phenomenons_us_vw`. Filter by event date range and phenomenon, "
            "review per-phenomenon summary cards, and use the emoji markers whose size "
            "shows the main metric; hover reveals the event, location, metric value, "
            "danger rating and dates."
        ),
    ),
)
