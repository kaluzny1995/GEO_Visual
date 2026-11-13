# GEO_Visual

Python 3.11 Streamlit dashboards for the GEO geographic-data pipeline.

## Overview

GEO_Visual is the presentation layer of the GIS data pipeline, sitting alongside
[GEO_Download](https://github.com/kaluzny1995/GEO_Download),
[GEO_ETL](https://github.com/kaluzny1995/GEO_ETL),
[GEO_API](https://github.com/kaluzny1995/GEO_API) and
[GEO_E2E](https://github.com/kaluzny1995/GEO_E2E). It reads dashboard views built over
the analysis-ready tables that GEO_ETL loads into Supabase (PostgreSQL) and turns them
into interactive Streamlit pages.

The repository ships a welcome page, eight natural-phenomenon metric dashboards
and nine area phenomenon maps. The timeline dashboards cover avalanche,
drought, earthquake, fire, flood, iceberg, storm and volcano; each pairs a
daily-snapshot **timeline** from the matching `geo.metrics_*_vw` view with a
**value distribution histogram**, one pair per metric. The maps plot POIs from
the `geo.phenomenons_<area>_vw` views for the United States, Canada, Central &
South America, Europe, Africa, Asia, Australia & Oceania, Russia and
international waters. Supabase connection helpers, a shared sidebar and
performance guardrails are used by every page and are ready for the remaining
data exploration and data-quality pages.

GEO_Visual reads directly from Supabase Postgres rather than routing analytical
queries through GEO_API: one network hop, full SQL pushdown and no JSON
serialization. The app queries views in the `geo` schema only — base and `_etl`
tables remain owned by GEO_ETL. See [Performance](docs/performance.md) for the
trade-offs and the guardrails that keep large result sets out of the Streamlit process.

> Status: welcome page, Supabase connectivity, all eight metric timelines/distributions and all nine area phenomenon maps are in place.

## Features

- **Streamlit multipage app** — the welcome page (`app.py`) with collapsible
  dashboard/map cards plus two collapsible sidebar groups: **Metric timelines
  and distributions** and **Phenomenon maps**; the main tab is labeled **Start**
  while the entrypoint script stays `app.py`
- **Avalanche metrics timeline & distribution** — one Plotly line chart and one
  value histogram per metric from `geo.metrics_avalanche_vw`, with a snapshot
  date range and mean, median, maximum, total or observation-count statistics;
  every recorded value is plotted, so the `danger_level = -1` (no rating)
  off-season snapshots stay visible, every chart spans the selected timeline and
  missing periods are shaded, with missing ranges listed below each chart, and
  the mean view also shows the observed min-max band across forecast zones
- **Drought metrics timeline & distribution** — the same timeline/histogram
  engine over `geo.metrics_drought_vw`, covering drought `area` and any future
  numeric drought metric with the same filters, missing-period shading and CSV
  export
- **Earthquake metrics timeline & distribution** — the same engine over
  `geo.metrics_earthquake_vw`, covering magnitude (`Mw`), depth, station counts
  and any future numeric earthquake metric; the one-observation `mlr` magnitude
  scale is hidden as too sparse to chart
- **Fire, flood, iceberg, storm and volcano timelines & distributions** — the
  remaining `geo.metrics_*_vw` views with the same filters, statistics,
  histograms, missing-period shading and CSV export; fire shows `area` and
  `percent_contained` (`geometry_count` hidden), flood shows `discharge`,
  `threshold` and `exceedance_ratio` (`baseline_days` and `magnitude` hidden),
  storm exposes all of its series, iceberg shows surface/geometry, and volcano
  shows `vei` and `vnum` (casualties, damage and magnitude hidden)
- **Area phenomenon maps** — nine POI maps from the
  `geo.phenomenons_<area>_vw` views with event date ranges, emoji markers,
  individually configured marker-size ranges per phenomenon, summary cards with
  POI count, mean main metric and the top state/province/country/area using full
  names, a framed map area, a geo-specific projection, structured hover metrics,
  dynamic category filters and an earthquake magnitude threshold; each metric
  has its own dark-theme text colour scale, the emoji size/text colour legend
  sits below each map and the **Phenomenon locations for &lt;area&gt;** heading
  sits above the filters
- **Shared map engine** — `dashboard/phenomenon_map.py` renders all nine area
  maps; `dashboard/map_configs.py` keeps each page's view, title, icon, region
  field, projection and zoom settings small and declarative, and
  `dashboard/region_names.py` converts ISO codes to full country/region names
- **Value distribution histograms** — each timeline is paired with a 20-bin
  histogram of every raw value for the visible metric series in the selected date range, computed from
  the shared `sql/metrics_distribution.sql` query; MLlib-predicted values are
  overlaid as a separate pink series
- **Predicted gaps** — GEO_ETL's `geo.prediction_etl` fills dates with no
  observation using PySpark MLlib; the timelines draw those points as pink
  diamonds with dashed segments and a **Show predicted values** checkbox, while
  the **Observations** KPI stays observed-only
- **Shared timeline engine** — `dashboard/metrics_timeline.py` renders all eight
  timeline/distribution dashboards; per-view configurations and SQL scripts keep
  the page code small
- **Supabase connectivity** — SQLAlchemy 2.0 sync engine with the psycopg 3 driver,
  credentials from `.env`, TLS enforced and prepared statements disabled for the
  Supabase transaction pooler
- **Views-only data contract** — dashboard queries read views in the `geo` schema,
  never GEO_ETL's base or `_etl` tables
- **Parametrized SQL files** — dashboard queries live in `sql/*.sql` with named
  bind parameters (`:start_date`, `:end_date`, `:min_magnitude`) and are loaded
  by `utils/sql.py`
- **Connection helpers** — one pooled engine per Streamlit process (`st.cache_resource`),
  a cached connection status with a sidebar **Recheck connection** button, and a
  bounded query cache shared by the dashboard pages
- **Large-data guardrails** — every query has a row cap and a PostgreSQL statement
  timeout, and `cached_query()` caches only bounded, chart-sized results
- **Typed configuration** — Pydantic models for `config.json` and `SUPABASE_DB_*`
  environment variables
- **Dark themed UI** — shared Streamlit dark theme in `.streamlit/config.toml`
  with contrast-checked text, links, code blocks and a chart/map palette that
  stays readable on the dark background
- **Dockerized deployment** — the `geo_streamlit` image in GEO_E2E serves the app on
  port 8501, with Supabase credentials injected at runtime
- **Dev tooling** — ruff (lint + format), mypy, pytest and tox
- **Tests without a database** — mocked engine, chart/map builders and Streamlit's
  `AppTest` cover the welcome page, all timelines/distributions (including the
  predicted series and toggle) and all nine area maps

## Dashboards

- **Avalanche metrics timeline & distribution** — daily changes of
  `danger_level`, avalanche `size` and any other metric published in
  `geo.metrics_avalanche_vw`, with a value histogram for each metric. See
  [Avalanche metrics timeline & distribution](docs/avalanche-timeline.md) for
  the query, aggregation semantics and how the `danger_level = -1` (no rating)
  state is included in the full snapshot range.
- **Drought metrics timeline & distribution** — daily changes of drought `area`
  and any other numeric metric published in `geo.metrics_drought_vw`, with a
  value histogram for each metric. See
  [Drought metrics timeline & distribution](docs/drought-timeline.md) for the
  view, SQL scripts and page behavior.
- **Earthquake metrics timeline & distribution** — daily changes of `magnitude`,
  `depth`, `nst` and any other numeric metric published in
  `geo.metrics_earthquake_vw`, with a value histogram for each metric. See
  [Earthquake metrics timeline & distribution](docs/earthquake-timeline.md) for
  the view, SQL scripts and page behavior.
- **Fire, flood, iceberg, storm and volcano timelines & distributions** — the
  remaining natural-phenomenon views (`geo.metrics_fire_vw`,
  `geo.metrics_flood_vw`, `geo.metrics_iceberg_vw`, `geo.metrics_storm_vw`,
  `geo.metrics_volcano_vw`) with the same per-metric timelines, histograms and
  filters; Volcano Number (`vnum`) now receives predictions for its missing
  dates as well. See
  [Fire, flood, iceberg, storm and volcano timelines & distributions](docs/phenomena-timelines.md)
  for the current metric series and SQL files.

## Maps

- **United States** — 🇺🇸 `geo.phenomenons_us_vw`
- **Canada** — 🇨🇦 `geo.phenomenons_ca_vw`
- **Central & South America** — 🌎 `geo.phenomenons_cs_amer_vw`
- **Europe** — 🇪🇺 `geo.phenomenons_europe_vw`
- **Africa** — 🌍 `geo.phenomenons_africa_vw`
- **Asia** — 🌏 `geo.phenomenons_asia_vw`
- **Australia & Oceania** — 🇦🇺 `geo.phenomenons_aus_oc_vw`
- **Russia** — 🇷🇺 `geo.phenomenons_ru_vw`
- **International waters** — 🌊 `geo.phenomenons_waters_vw`

Every map supports an event date range, dynamic phenomenon categories, a
framed geo-specific map, per-phenomenon summary cards, emoji markers whose size
encodes the normalised main metric, a size/text-colour legend below the map,
hover details and an earthquake magnitude threshold. Tooltips use full country
and region names, format the main metric as **Metric: value unit**, show every
other metric on its own line and hide danger/percentile fields. See
[Phenomenon maps](docs/phenomenon-maps.md) for the shared deduplication rules,
main-metric mapping, per-phenomenon size ranges, text colour scales, projections
and SQL.

## Tech Stack

| Component        | Technology                                  |
|------------------|---------------------------------------------|
| Language         | Python 3.11                                 |
| UI framework     | Streamlit >= 1.51                           |
| Dataframes       | pandas >= 2.0                               |
| Data access      | Direct PostgreSQL (Supabase) views, read-only role recommended |
| Database         | PostgreSQL (Supabase) via SQLAlchemy 2.0    |
| DB driver        | psycopg 3 (`psycopg[binary] >= 3.1`)        |
| Configuration    | Pydantic >= 2.0, python-dotenv >= 1.0       |
| Charting         | Plotly >= 5.20                              |
| Testing          | pytest >= 7.0, Streamlit `AppTest`          |
| Lint / format    | ruff >= 0.6                                 |
| Type checking    | mypy >= 1.10                                |
| Check runner     | tox >= 4.0                                  |
| Environment      | Conda — `geo_visual_311`; Docker image `geo_streamlit` |

## Setup & development

See [Setup, configuration and development](docs/setup.md) for the repository layout,
prerequisites, quick start, Docker deployment, `config.json`, performance guardrails,
tox environments and the test suite.

## Related Projects

GEO_Visual is one layer of the GIS data pipeline. The projects sit as siblings under
`GeographicData/`:

- **[GEO_Download](https://github.com/kaluzny1995/GEO_Download)** — fetches raw
  geospatial data from public APIs into dated CSVs.
- **[GEO_ETL](https://github.com/kaluzny1995/GEO_ETL)** — PySpark ETL that loads the
  CSVs into Supabase and writes the `geo.*` tables behind the views this app reads.
- **[GEO_API](https://github.com/kaluzny1995/GEO_API)** — FastAPI REST layer over the
  same Supabase data.
- **[GEO_E2E](https://github.com/kaluzny1995/GEO_E2E)** — Airflow and Docker Compose
  orchestration for the pipeline; it also builds and runs this app as the
  `geo_streamlit` service on port 8501.
- **[GEO_APP](https://github.com/kaluzny1995/GEO_APP)** — React dashboard for the API.
