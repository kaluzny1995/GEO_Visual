# Phenomenon maps

The **Phenomenon maps** sidebar group contains nine natural-phenomenon POI
dashboards. Each map reads one area view from the `geo` schema and shares the
same date filter, summary cards, emoji markers, per-phenomenon size scale, map
frame and hover tooltip.

| Page | View | Icon |
|------|------|------|
| United States | `geo.phenomenons_us_vw` | 🇺🇸 |
| Canada | `geo.phenomenons_ca_vw` | 🇨🇦 |
| Central & South America | `geo.phenomenons_cs_amer_vw` | 🌎 |
| Europe | `geo.phenomenons_europe_vw` | 🇪🇺 |
| Africa | `geo.phenomenons_africa_vw` | 🌍 |
| Asia | `geo.phenomenons_asia_vw` | 🌏 |
| Australia & Oceania | `geo.phenomenons_aus_oc_vw` | 🇦🇺 |
| Russia | `geo.phenomenons_ru_vw` | 🇷🇺 |
| International waters | `geo.phenomenons_waters_vw` | 🌊 |

Open them at **<http://localhost:8501> → Phenomenon maps**, from the collapsible
welcome-page map cards, or from the page files in `pages/9_*` through
`pages/17_*`.

## Data source

Every area view is a point-location view written by GEO_ETL from
`geo.union_etl` and shares the same columns:

| Column | Meaning |
|--------|---------|
| `event_category` / `event_subcategory` | Phenomenon type and subtype |
| `event_ndesc` | Event name plus description |
| `latitude` / `longitude` | Point location |
| `country_code` / `state_province` / `place_location` | Country, state and place labels |
| `danger_rating` | Shared severity label (`no_rating` … `extreme`) |
| `metric_name` / `metric_value` / `metric_unit` | Main metric and unit |
| `other_metrics` | Additional metrics as a compact string |
| `event_start_date` / `event_end_date` | Event dates |

The views contain daily snapshot duplicates. The map query keeps **one POI per
event**, choosing the row with the highest main metric value for each
`event_ndesc` + location (volcanoes are grouped by `place_location` + location
because their descriptions change between snapshots). Events that only carry a
secondary metric stay on the map with no main-metric value, so no location is
lost.

## Page layout

From top to bottom every map page shows:

1. the area icon and dashboard title, plus the view description
2. **Phenomenon locations for &lt;area&gt;** as a heading directly above the filters
3. the event date range, phenomenon multi-select and earthquake threshold
4. one summary card per phenomenon
5. the framed area map
6. the emoji marker-size legend below the map
7. the size and earthquake-threshold captions

The Plotly figure itself has no title; the locations heading above the filters
takes that role.

### Summary cards

Each selected phenomenon gets a card above the map containing:

- **POI count** — deduplicated events in the selected date range and filters
- **Mean main metric** — the mean of the phenomenon's main metric with its unit
- **Top region** — the configured geographic column with the highest POI count:
  - United States: `state_province` (label **Top state**)
  - Canada: `state_province` (label **Top province**)
  - Russia: `state_province` (label **Top region**)
  - Central & South America, Europe, Africa, Asia and Australia & Oceania:
    `country_code` (label **Top country**)
  - International waters: `place_location` (label **Top area**)

When the configured column is empty, the card falls back to the area name. The
cards use responsive CSS grid columns with larger count figures and smaller
labels and detail rows.

### Emoji size legend

The size legend sits **under the map**. For every phenomenon it shows:

- the phenomenon emoji rendered at that phenomenon's minimum marker size,
  followed by the lowest observed main-metric value
- an arrow
- the same emoji rendered at the phenomenon's maximum marker size, followed by
  the highest observed main-metric value
- the main metric name and unit

The legend uses emoji sizes rather than dots, so the encoding matches the map
markers exactly. Phenomena without any main-metric values show `no values` at
the minimum emoji size.

## Main metric and marker style

| Emoji | Phenomenon | Main metric | Unit | Emoji size range |
|-------|------------|-------------|------|------------------|
| ❄️ | Avalanche | `size` | destructive size class | 10–20 px |
| 🌵 | Drought | `area` | km² | 12–22 px |
| 🏚️ | Earthquake | `magnitude` | Mw | 6–14 px |
| 🔥 | Fire | `area` | km² | 9–18 px |
| 🌊 | Flood | `discharge` | m³/s | 10–21 px |
| 🧊 | Iceberg | `surface` | N/m² | 13–23 px |
| ⛈️ | Storm | `wind speed` | km/h | 11–21 px |
| 🌋 | Volcano | `vei` | VEI | 12–24 px |

The ranges are configured individually per phenomenon in
`dashboard/phenomenon_map.py` (`PhenomenonStyle.min_size` / `max_size`), so
dense layers such as earthquakes can use smaller emojis while icebergs and
volcanoes remain prominent.

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

Points without a main metric value — for example unrated avalanche zones or
volcanoes without VEI — are shown with the same emoji at that phenomenon's
minimum size and reduced opacity.

## Filters

- **Event date range** — defaults to the first and last `event_start_date` in
  the area view. Both dates are inclusive; the map query selects events whose
  start date falls inside the range.
- **Phenomena** — multi-select containing only the categories present in that
  area view. The date-bounds query also returns the available categories, so no
  empty series appear in the selector.
- **Minimum earthquake magnitude** — appears when Earthquake is selected.
  Defaults to **M2.5**; lower it to show smaller earthquakes or raise it to
  reduce clutter.

The map query is capped at 50,000 POIs.

## Geographic projections

Each area defines its Plotly scope and projection in
`dashboard/map_configs.py`:

| Area | Scope / projection |
|------|--------------------|
| United States | `usa` / `albers usa` |
| Canada | `north america` / `natural earth`, focused on Canadian longitudes and latitudes |
| Central & South America | `south america` / `natural earth` |
| Europe | `europe` / `natural earth` |
| Africa | `africa` / `natural earth` |
| Asia | `asia` / `natural earth` |
| Australia & Oceania | `world` / `equirectangular`, dateline-wrapped and focused on the Pacific |
| Russia | `world` / `orthographic`, centred on Russia |
| International waters | `world` / `natural earth` |

Every map adds a visible rectangle around the map area, drawn with a
`xref="paper"` / `yref="paper"` Plotly shape in a contrasting slate outline.

## Hover tooltip

Hovering a point shows:

- emoji and event title
- place and state
- main metric name, value and unit
- danger rating
- event dates
- a compact preview of `other_metrics` when present

## Query

Both shared scripts use a `{view_name}` placeholder filled from the area
configuration. The date-bounds query returns the first and last event date plus
the available categories:

```sql
SELECT to_char(min(event_start_date), 'YYYY-MM-DD') AS min_date,
       to_char(max(event_start_date), 'YYYY-MM-DD') AS max_date,
       array_agg(DISTINCT event_category ORDER BY event_category) AS categories
FROM {view_name}
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND event_start_date IS NOT NULL;
```

The map query from `sql/phenomenons_map.sql` binds `:min_magnitude`,
`:start_date` and `:end_date` and is capped at 50,000 rows:

```sql
WITH main_metric AS (
    SELECT event_category,
           event_subcategory,
           event_ndesc,
           split_part(event_ndesc, E'\n\n', 1) AS event_title,
           latitude,
           longitude,
           country_code,
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
               WHEN 'Iceberg' THEN metric_name = 'surface'
               WHEN 'Storm' THEN metric_name = 'wind speed'
               WHEN 'Volcano' THEN metric_name = 'vei'
               ELSE FALSE
           END AS is_main_metric
    FROM {view_name}
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
               ORDER BY is_main_metric DESC,
                        metric_value DESC NULLS LAST,
                        event_start_date DESC NULLS LAST
           ) AS row_number
    FROM main_metric
)
SELECT event_category,
       event_subcategory,
       event_title,
       latitude,
       longitude,
       country_code,
       state_province,
       place_location,
       danger_rating,
       CASE WHEN is_main_metric THEN metric_name END AS metric_name,
       CASE WHEN is_main_metric THEN metric_value END AS metric_value,
       CASE WHEN is_main_metric THEN metric_unit END AS metric_unit,
       other_metrics,
       event_start_date,
       event_end_date
FROM ranked
WHERE row_number = 1
  AND (
      event_category <> 'Earthquake'
      OR (is_main_metric AND metric_value >= :min_magnitude)
  )
ORDER BY event_category, event_start_date DESC NULLS LAST;
```

The query selects only the columns needed for the map, tooltip and cards and
follows the [views-only contract](performance.md).

## Code map

| File | Role |
|------|------|
| `pages/9_United_States_Map.py` … `pages/17_International_Waters_Map.py` | One thin Streamlit page per area |
| `dashboard/map_configs.py` | Area metadata: view, page, title, icon, region field and projection |
| `dashboard/phenomenon_map.py` | Shared map query, normalisation, cards, size legend, hover text and Plotly figure |
| `dashboard/catalog.py` | Builds `MAPS` cards from the area configurations |
| `sql/phenomenons_map.sql` | Shared deduplicated POI query |
| `sql/phenomenons_map_date_bounds.sql` | Shared date/category metadata query |
| `utils/layout.py` | Shared page config and collapsible **Phenomenon maps** navigation |
| `test/test_phenomenon_map.py` | Metadata, SQL, sizes, cards, legend, projections and all nine pages |

## Testing

The maps are covered without a live database:

```bash
pytest test/test_phenomenon_map.py test/test_sql.py test/test_app.py
```

Tests cover metadata loading and category ordering, per-area SQL formatting,
query parameter forwarding, per-phenomenon intensity and emoji size ranges,
summary-card region fields, the emoji size legend, map frames and projections,
dateline wrapping, missing-metric markers, empty states, the page date filter
and every area page through Streamlit's `AppTest`.
