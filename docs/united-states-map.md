# United States phenomenon map

The **Phenomenon maps → United States** page plots natural-phenomenon
locations across the United States from `geo.phenomenons_us_vw`. It is the
first map dashboard in GEO_Visual and complements the per-phenomenon metric
timelines and distributions.

Open it at **<http://localhost:8501> → United States**, from the welcome-page
map card, or via `pages/9_United_States_Map.py` in the source tree.

## Data source

`geo.phenomenons_us_vw` is the US-only, point-location view written by GEO_ETL
from `geo.union_etl`. It carries:

| Column | Meaning |
|--------|---------|
| `event_category` / `event_subcategory` | Phenomenon type and subtype |
| `event_ndesc` | Event name plus description |
| `latitude` / `longitude` | Point location |
| `state_province` / `place_location` | State and place label |
| `danger_rating` | Shared severity label (`no_rating` … `extreme`) |
| `metric_name` / `metric_value` / `metric_unit` | Main metric and unit |
| `other_metrics` | Additional metrics as a compact string |
| `event_start_date` / `event_end_date` | Event dates |

The view contains daily snapshot duplicates. The map query keeps **one POI per
event**, choosing the row with the highest main metric value for each
`event_ndesc` + location (volcanoes are grouped by `place_location` + location
because their descriptions change between snapshots).

## Main metric and marker style

| Emoji | Phenomenon | Main metric | Unit |
|-------|------------|-------------|------|
| ❄️ | Avalanche | `size` | destructive size class |
| 🌵 | Drought | `area` | km² |
| 🏚️ | Earthquake | `magnitude` | Mw |
| 🔥 | Fire | `area` | km² |
| 🌊 | Flood | `discharge` | m³/s |
| ⛈️ | Storm | `wind speed` | km/h |
| 🌋 | Volcano | `vei` | VEI |

Emojis are the actual markers and appear in the phenomenon selector, the
Plotly legend and every tooltip.

## Size scale

Metric units differ between phenomena, so size cannot use one global numeric
range. Each phenomenon's main metric is normalised to **0–1 within that
phenomenon**:

- 0 = lowest observed main metric value in the current selection
- 1 = highest observed main metric value in the current selection

**Marker size is the intensity indicator**: small emoji = low, large emoji =
high. Emojis identify the phenomenon and keep their native colours; there is
no colour scale. A size legend sits to the right of the map, and the legend
table below it lists the actual observed range and unit for each phenomenon.

Points without a main metric value — currently unrated avalanche zones — are
shown with the same emoji at the smallest size and reduced opacity.

## Filters

- **Phenomena** — multi-select, defaulting to all seven phenomena.
- **Minimum earthquake magnitude** — appears when Earthquake is selected.
  Defaults to **M2.5**; lower it to show smaller earthquakes or raise it to
  reduce clutter. The query caps the map at 50,000 POIs.

## Hover tooltip

Hovering a point shows:

- emoji and event title
- place and state
- main metric name, value and unit
- danger rating
- event dates
- a compact preview of `other_metrics` when present

## Query

The map uses one guarded query from `sql/phenomenons_us_map.sql` through
`utils.database.cached_query()`:

```sql
WITH main_metric AS (
    SELECT event_category,
           event_subcategory,
           split_part(event_ndesc, E'\n\n', 1) AS event_title,
           latitude,
           longitude,
           state_province,
           place_location,
           danger_rating,
           metric_name,
           metric_value,
           metric_unit,
           other_metrics,
           event_start_date,
           event_end_date,
           CASE event_category
               WHEN 'Avalanche' THEN metric_name = 'size'
               WHEN 'Drought' THEN metric_name = 'area'
               WHEN 'Earthquake' THEN metric_name = 'magnitude' AND metric_unit = 'Mw'
               WHEN 'Fire' THEN metric_name = 'area'
               WHEN 'Flood' THEN metric_name = 'discharge'
               WHEN 'Storm' THEN metric_name = 'wind speed'
               WHEN 'Volcano' THEN metric_name = 'vei'
               ELSE FALSE
           END AS is_main_metric
    FROM geo.phenomenons_us_vw
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
),
ranked AS (
    SELECT main_metric.*,
           row_number() OVER (
               PARTITION BY event_category,
                            CASE
                                WHEN event_category = 'Volcano' THEN place_location
                                ELSE event_ndesc
                            END,
                            latitude,
                            longitude
               ORDER BY metric_value DESC NULLS LAST,
                        event_start_date DESC NULLS LAST
           ) AS row_number
    FROM main_metric
    WHERE is_main_metric
)
SELECT event_category,
       event_subcategory,
       event_title,
       latitude,
       longitude,
       state_province,
       place_location,
       danger_rating,
       metric_name,
       metric_value,
       metric_unit,
       other_metrics,
       event_start_date,
       event_end_date
FROM ranked
WHERE row_number = 1
  AND (event_category <> 'Earthquake' OR metric_value >= :min_magnitude)
ORDER BY event_category, event_start_date DESC NULLS LAST;
```

The query binds `:min_magnitude` and is capped at 50,000 rows. It selects only
the columns needed for the map and tooltip and follows the
[views-only contract](performance.md).

## Page behaviour

- US Albers projection with dark land, state and coastline outlines
- One map trace per phenomenon with emoji text markers and a category legend
- Emoji markers with a normalised main-metric size scale
- Category multi-select and earthquake magnitude threshold
- Small, low-opacity points for missing main metric values
- Legend table with observed metric ranges and POI counts
- Empty and error states for an empty selection or failed query

## Code map

| File | Role |
|------|------|
| `pages/9_United_States_Map.py` | Streamlit page entry — page config, shared sidebar, render call |
| `dashboard/us_map.py` | Query loading, normalisation, hover text and Plotly map builder |
| `dashboard/catalog.py` | `MAPS` metadata for the welcome card and **Phenomenon maps** navigation |
| `sql/phenomenons_us_map.sql` | Deduplicated US POI query with `:min_magnitude` |
| `utils/layout.py` | Shared page config and collapsible **Phenomenon maps** navigation |
| `test/test_us_map.py` | Map query, intensity, tooltip, figure and page tests |

## Testing

The map is covered without a live database:

```bash
pytest test/test_us_map.py test/test_sql.py
```

Tests cover query parameter forwarding, per-phenomenon intensity
normalisation, emoji text markers, hover text, size scale, missing-metric
markers, empty-map annotations and the page controls.
