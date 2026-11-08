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


DASHBOARDS: Final[tuple[DashboardCard, ...]] = (
    DashboardCard(
        page_path="pages/1_Avalanche_Timeline.py",
        nav_label="Avalanche Timeline",
        title="Avalanche metrics timeline",
        icon="❄️",
        description=(
            "Daily snapshots from `geo.metrics_avalanche_vw`: avalanche danger levels, "
            "destructive size and any other numeric metric published by GEO_ETL. "
            "Each metric gets its own linear timeline, with a selectable date range and "
            "mean, median, maximum, total or observation-count statistic. Periods without "
            "observations are shaded and labelled, and `danger_level = -1` (no rating) "
            "is shown as recorded."
        ),
    ),
    DashboardCard(
        page_path="pages/2_Drought_Timeline.py",
        nav_label="Drought Timeline",
        title="Drought metrics timeline",
        icon="🌵",
        description=(
            "Daily snapshots from `geo.metrics_drought_vw`: drought area and any other "
            "numeric metric published by GEO_ETL. Each metric gets its own linear "
            "timeline, with a selectable date range and mean, median, maximum, total or "
            "observation-count statistic. Periods without observations are shaded and "
            "labelled."
        ),
    ),
    DashboardCard(
        page_path="pages/3_Earthquake_Timeline.py",
        nav_label="Earthquake Timeline",
        title="Earthquake metrics timeline",
        icon="🏚️",
        description=(
            "Daily snapshots from `geo.metrics_earthquake_vw`: magnitude, depth, station "
            "counts and any other numeric metric published by GEO_ETL. Each metric gets "
            "its own linear timeline, with a selectable date range and mean, median, "
            "maximum, total or observation-count statistic. Periods without observations "
            "are shaded and labelled."
        ),
    ),
    DashboardCard(
        page_path="pages/4_Fire_Timeline.py",
        nav_label="Fire Timeline",
        title="Fire metrics timeline",
        icon="🔥",
        description=(
            "Daily snapshots from `geo.metrics_fire_vw`: burned area, percent contained, "
            "geometry counts and any other numeric fire metric published by GEO_ETL. Each "
            "metric gets its own linear timeline, with a selectable date range and mean, "
            "median, maximum, total or observation-count statistic. Periods without "
            "observations are shaded and labelled."
        ),
    ),
    DashboardCard(
        page_path="pages/5_Flood_Timeline.py",
        nav_label="Flood Timeline",
        title="Flood metrics timeline",
        icon="🌊",
        description=(
            "Daily snapshots from `geo.metrics_flood_vw`: discharge, threshold, baseline "
            "days, exceedance ratio, magnitude and any other numeric flood metric. Each "
            "metric gets its own linear timeline, with a selectable date range and mean, "
            "median, maximum, total or observation-count statistic. Periods without "
            "observations are shaded and labelled."
        ),
    ),
    DashboardCard(
        page_path="pages/6_Iceberg_Timeline.py",
        nav_label="Iceberg Timeline",
        title="Iceberg metrics timeline",
        icon="🧊",
        description=(
            "Daily snapshots from `geo.metrics_iceberg_vw`: surface area, geometry counts "
            "and any other numeric iceberg metric published by GEO_ETL. Each metric gets "
            "its own linear timeline, with a selectable date range and mean, median, "
            "maximum, total or observation-count statistic. Periods without observations "
            "are shaded and labelled."
        ),
    ),
    DashboardCard(
        page_path="pages/7_Storm_Timeline.py",
        nav_label="Storm Timeline",
        title="Storm metrics timeline",
        icon="⛈️",
        description=(
            "Daily snapshots from `geo.metrics_storm_vw`: wind speed, gusts, pressure, "
            "direction, landfall, distance to land, geometry counts and any other numeric "
            "storm metric. Each metric gets its own linear timeline, with a selectable "
            "date range and mean, median, maximum, total or observation-count statistic. "
            "Periods without observations are shaded and labelled."
        ),
    ),
    DashboardCard(
        page_path="pages/8_Volcano_Timeline.py",
        nav_label="Volcano Timeline",
        title="Volcano metrics timeline",
        icon="🌋",
        description=(
            "Daily snapshots from `geo.metrics_volcano_vw`: VEI, Smithsonian volcano "
            "number, casualties, damage, magnitude and any other numeric volcano metric. "
            "Each metric gets its own linear timeline, with a selectable date range and "
            "mean, median, maximum, total or observation-count statistic. Periods without "
            "observations are shaded and labelled."
        ),
    ),
)
