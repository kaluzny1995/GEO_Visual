# United States phenomenon map

The **Phenomenon maps → United States** page plots natural-phenomenon
locations across the United States from `geo.phenomenons_us_vw`. It is the
first map dashboard in GEO_Visual and complements the per-phenomenon metric
timelines and distributions. The dashboard, sidebar tab and welcome card use
the 🇺🇸 icon.

Open it at **<http://localhost:8501> → United States**, from the collapsible
welcome-page map card, or via `pages/9_United_States_Map.py` in the source tree.

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

## Page layout

From top to bottom the page shows:

1. the 🇺🇸 title and a short description
2. the event date range, phenomenon multi-select and earthquake threshold
3. one summary card per phenomenon
4. the emoji marker-size legend with each phenomenon's observed value range
5. the framed US map

### Summary cards

Each selected phenomenon gets a card above the map containing:

- **POI count** — deduplicated events in the selected date range and filters
- **Mean main metric** — the mean of the phenomenon's main metric with its unit
- **Top region** — the `state_province` with the highest POI count, plus that
  count; when no state is recorded, the card falls back to **United States**

The cards use responsive CSS grid columns with larger count figures and smaller
labels and detail rows.

### Emoji size legend

The size legend sits **above the map**. For every phenomenon it shows:

- the phenomenon emoji rendered at that phenomenon's minimum marker size,
  followed by the lowest observed main-metric value
- an arrow
- the same emoji rendered at the phenomenon's maximum marker size, followed by
  the highest observed main-metric value
- the main metric name and unit

For example, a Fire range of 10–30 km² is shown with a small 🔥 next to `10`
and a large 🔥 next to `30`. The legend uses emoji sizes rather than dots, so
the encoding matches the map markers exactly. Phenomena without any main-metric
values show `no values` at the minimum emoji size.

## Main metric and marker style

| Emoji | Phenomenon | Main metric | Unit | Emoji size range |
|-------|------------|-------------|------|------------------|
| ❄️ | Avalanche | `size` | destructive size class | 10–20 px |
| 🌵 | Drought | `area` | km² | 12–22 px |
| 🏚️ | Earthquake | `magnitude` | Mw | 6–14 px |
| 🔥 | Fire | `area` | km² | 9–18 px |
| 🌊 | Flood | `discharge` | m³/s | 10–21 px |
| ⛈️ | Storm | `wind speed` | km/h | 11–21 px |
| 🌋 | Volcano | `vei` | VEI | 12–24 px |

The ranges are configured individually per phenomenon in
`dashboard/us_map.py` (`PhenomenonStyle.min_size` / `max_size`), so dense layers
such as earthquakes can use smaller emojis while volcanoes remain prominent.

## Size scale

Metric units differ between phenomena, so size cannot use one global numeric
range. Each phenomenon's main metric is normalised to **0–1 within that
phenomenon**:

- 0 = lowest observed main metric value in the current selection
- 1 = highest observed main metric value in the current selection

**Marker size is the intensity indicator**: small emoji = low, large emoji =
high. Each phenomenon maps that 0–1 intensity onto its own configured emoji
size range. Emojis identify the phenomenon and keep their native colours; there
is no colour scale.

Points without a main metric value — currently unrated avalanche zones — are
shown with the same emoji at that phenomenon's minimum size and reduced opacity.

## Filters

- **Event date range** — defaults to the first and last `event_start_date` in
  the view. Both dates are inclusive; the map query selects events whose start
  date falls inside the range. The bounds come from
  `sql/phenomenons_us_map_date_bounds.sql`.
- **Phenomena** — multi-select, defaulting to all seven phenomena.
- **Minimum earthquake magnitude** — appears when Earthquake is selected.
  Defaults to **M2.5**; lower it to show smaller earthquakes or raise it to
  reduce clutter.

The map query is capped at 50,000 POIs.

## Map frame

The Plotly figure adds a visible rectangle around the map area using a
`xref="paper"` / `yref="paper"` shape. The frame uses a slate outline that
contrasts with the dark page background and is drawn below the map traces.

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
           event_ndesc,
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
      AND event_start_date >= CAST(:start_date AS date)
      AND event_start_date < CAST(:end_date AS date) + INTERVAL '1 day'
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

The query binds `:min_magnitude`, `:start_date` and `:end_date` and is capped at
50,000 rows. It selects only the columns needed for the map, tooltip and cards
and follows the [views-only contract](performance.md).

## Page behaviour

- US Albers projection with dark land, state and coastline outlines
- Visible Plotly rectangle frame around the map area
- Emoji markers with per-phenomenon marker-size ranges
- Normalised main-metric size scale and an emoji size legend above the map
- Summary cards with POI count, mean main metric and top region
- Event date range, category multi-select and earthquake magnitude threshold
- Small, low-opacity points for missing main metric values
- Empty and error states for unavailable date bounds, an empty selection or a
  failed query

## Code map

| File | Role |
|------|------|
| `pages/9_United_States_Map.py` | Streamlit page entry — page config, shared sidebar, render call |
| `dashboard/us_map.py` | Date/filter loading, normalisation, cards, size legend, hover text and Plotly map builder |
| `dashboard/catalog.py` | `MAPS` metadata for the welcome card and **Phenomenon maps** navigation |
| `sql/phenomenons_us_map.sql` | Deduplicated US POI query with `:min_magnitude`, `:start_date`, `:end_date` |
| `sql/phenomenons_us_map_date_bounds.sql` | First and last event start date for the date picker |
| `utils/layout.py` | Shared page config and collapsible **Phenomenon maps** navigation |
| `test/test_us_map.py` | Date bounds, map query, sizes, cards, legend, tooltip, figure and page tests |

## Testing

The map is covered without a live database:

```bash
pytest test/test_us_map.py test/test_sql.py
```

Tests cover date-bounds loading, query parameter forwarding, per-phenomenon
intensity normalisation and emoji size ranges, summary-card content, the emoji
size legend, hover text, the map frame, missing-metric markers, empty-map
annotations, the page date filter and the page controls.
