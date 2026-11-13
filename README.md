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
  filters. See
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

## Project Structure

```text
GEO_Visual/
├── app.py                                  # Streamlit entry point, welcome page and dashboard/map cards
├── pages/
│   ├── 1_Avalanche_Timeline.py             # Avalanche dashboard page
│   ├── 2_Drought_Timeline.py               # Drought dashboard page
│   ├── 3_Earthquake_Timeline.py            # Earthquake dashboard page
│   ├── 4_Fire_Timeline.py                  # Fire dashboard page
│   ├── 5_Flood_Timeline.py                 # Flood dashboard page
│   ├── 6_Iceberg_Timeline.py               # Iceberg dashboard page
│   ├── 7_Storm_Timeline.py                 # Storm dashboard page
│   ├── 8_Volcano_Timeline.py               # Volcano dashboard page
│   ├── 9_United_States_Map.py              # United States phenomenon map page
│   ├── 10_Canada_Map.py                    # Canada phenomenon map page
│   ├── 11_Central_South_America_Map.py     # Central & South America map page
│   ├── 12_Europe_Map.py                    # Europe phenomenon map page
│   ├── 13_Africa_Map.py                    # Africa phenomenon map page
│   ├── 14_Asia_Map.py                      # Asia phenomenon map page
│   ├── 15_Australia_Oceania_Map.py         # Australia & Oceania map page
│   ├── 16_Russia_Map.py                    # Russia phenomenon map page
│   └── 17_International_Waters_Map.py      # International waters map page
├── dashboard/
│   ├── __init__.py
│   ├── metrics_timeline.py                 # Shared timeline engine and Plotly charts
│   ├── avalanche_timeline.py               # Avalanche dashboard configuration
│   ├── drought_timeline.py                 # Drought dashboard configuration
│   ├── earthquake_timeline.py              # Earthquake dashboard configuration
│   ├── fire_timeline.py                    # Fire dashboard configuration
│   ├── flood_timeline.py                   # Flood dashboard configuration
│   ├── iceberg_timeline.py                 # Iceberg dashboard configuration
│   ├── storm_timeline.py                   # Storm dashboard configuration
│   ├── volcano_timeline.py                 # Volcano dashboard configuration
│   ├── phenomenon_map.py                   # Shared area map engine
│   ├── map_configs.py                      # Area view, title, icon, region and projection metadata
│   ├── region_names.py                     # Full ISO country and first-level region names
│   └── catalog.py                          # Dashboard/map metadata for cards and navigation
├── sql/
│   ├── avalanche_metrics_date_bounds.sql   # Avalanche date picker bounds query
│   ├── avalanche_metrics_timeline.sql      # Parametrized avalanche timeline query
│   ├── drought_metrics_date_bounds.sql     # Drought date picker bounds query
│   ├── drought_metrics_timeline.sql        # Parametrized drought timeline query
│   ├── earthquake_metrics_date_bounds.sql  # Earthquake date picker bounds query
│   ├── earthquake_metrics_timeline.sql     # Parametrized earthquake timeline query
│   ├── fire_metrics_date_bounds.sql        # Fire date picker bounds query
│   ├── fire_metrics_timeline.sql           # Parametrized fire timeline query
│   ├── flood_metrics_date_bounds.sql       # Flood date picker bounds query
│   ├── flood_metrics_timeline.sql          # Parametrized flood timeline query
│   ├── iceberg_metrics_date_bounds.sql     # Iceberg date picker bounds query
│   ├── iceberg_metrics_timeline.sql        # Parametrized iceberg timeline query
│   ├── storm_metrics_date_bounds.sql       # Storm date picker bounds query
│   ├── storm_metrics_timeline.sql          # Parametrized storm timeline query
│   ├── volcano_metrics_date_bounds.sql     # Volcano date picker bounds query
│   ├── volcano_metrics_timeline.sql        # Parametrized volcano timeline query
│   ├── metrics_distribution.sql            # Shared raw values query for histograms
│   ├── phenomenons_map.sql                 # Shared deduplicated area POI query
│   └── phenomenons_map_date_bounds.sql     # Shared date and category metadata query
├── config.json                             # App metadata and database pool/query limits
├── error.py                                # QueryTooLargeError
├── .streamlit/
│   └── config.toml                         # Shared Streamlit theme
├── docs/
│   ├── avalanche-timeline.md               # Avalanche dashboard query and aggregation rules
│   ├── drought-timeline.md                 # Drought dashboard query and aggregation rules
│   ├── earthquake-timeline.md              # Earthquake dashboard query and aggregation rules
│   ├── phenomena-timelines.md              # Fire, flood, iceberg, storm and volcano timelines & distributions
│   ├── phenomenon-maps.md                  # All area maps: views, projections, cards and size scale
│   └── performance.md                      # Direct-Postgres rationale and views-only query rules
├── model/
│   └── config/
│       ├── app_config.py                   # config.json model
│       └── supabase_config.py              # SUPABASE_DB_* model and connection URL
├── provider/
│   └── supabase_postgres/
│       └── supabase_postgres_provider.py   # Pooled engine, guarded queries and schema introspection
├── utils/
│   ├── database.py                         # Cached provider, status and cached_query()
│   ├── layout.py                           # Shared page config, grouped sidebar nav and branding
│   └── sql.py                              # Loads sql/*.sql scripts
├── test/
│   ├── dashboard/                          # Shared engine and dashboard-config tests
│   ├── model/config/                       # Config parsing and env loading
│   ├── provider/supabase_postgres/         # Provider behavior with a mocked engine
│   ├── test_app.py                         # Welcome page via Streamlit AppTest
│   ├── test_metrics_pages.py               # All eight timeline and distribution pages via AppTest
│   ├── test_phenomenon_map.py              # All area maps: metadata, cards, legend, projections and pages
│   ├── test_database.py                    # Connection status handling
│   ├── test_project_layout.py              # Repository contract checks
│   └── test_sql.py                         # SQL files, bind parameters and loader
├── environment.yml                         # Conda environment geo_visual_311
├── pyproject.toml                          # ruff, pytest and mypy settings
└── tox.ini                                 # Isolated lint/test/typecheck environments
```

The Docker image definition (`geo_streamlit`) lives in
`GEO_E2E/docker/geo_streamlit/` because it builds from the sibling `GeographicData/`
context.

## Prerequisites

- **Conda** — for the Python 3.11 environment
- **Docker + Docker Compose** — optional, for the `geo_streamlit` service in GEO_E2E
- **Supabase credentials** — the same project used by GEO_ETL and GEO_API, provided
  through `.env` (never committed). A read-only role with `SELECT` on the dashboard
  views in the `geo` schema is recommended; see
  [Performance](docs/performance.md#read-only-database-role).

## Quick Start

```bash
# 1. Create and activate the conda environment (Python 3.11)
conda env create -f environment.yml
conda activate geo_visual_311

# 2. Configure Supabase (copy the template and fill in the values)
cp .env.example .env

# 3. Run the Streamlit app
streamlit run app.py
```

Streamlit opens at <http://localhost:8501>. The welcome page renders without a
database; the sidebar reports if Supabase is not configured. Open the
appropriate dashboard from the collapsible welcome cards, the **Metric
timelines and distributions** sidebar group, or the **Phenomenon maps** group.
Timelines read their matching `geo.metrics_*_vw` view and each map reads its
matching `geo.phenomenons_<area>_vw` view; without credentials or data each page
shows an empty state instead of failing.

### Docker (GEO_E2E stack)

GEO_Visual is also served by the `geo_streamlit` image in GEO_E2E. The container
writes `GEO_Visual/.env` from the Compose `SUPABASE_DB_*` environment at startup, so
no credentials are baked into the image:

```bash
cd ../GEO_E2E
./up.sh -d --build geo_streamlit   # preflight (six repos + Supabase .env), then compose up
```

The dashboard is then available at <http://localhost:8501>. Override the host port with
`GEO_VISUAL_HOST_PORT` in `GEO_E2E/.env`.

## Configuration

### Environment variables

`SupabaseConnectionConfig.from_env()` reads the same five variables as the sibling
projects. A `.env` file in the project root is loaded first; variables already set in
the environment take precedence.

| Variable                | Description                                              |
|-------------------------|----------------------------------------------------------|
| `SUPABASE_DB_USER`      | Database user, e.g. `postgres.<project-ref>`             |
| `SUPABASE_DB_PASSWORD`  | Database password                                        |
| `SUPABASE_DB_HOST`      | Supabase pooler hostname                                 |
| `SUPABASE_DB_PORT`      | Pooler port, typically `6543` for the transaction pooler |
| `SUPABASE_DB_NAME`      | Database name, typically `postgres`                      |

Copy `.env.example` to `.env` and take the values from the Supabase dashboard:
**Project → Connect → Connection pooling → Transaction pooler**. In the Docker
`geo_streamlit` service, the entrypoint writes this `.env` at container start from the
Compose environment, so credentials are never baked into an image layer.

### `config.json`

| Section    | Keys                                                                                                                                                                              | Purpose                                      |
|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| `app`      | `title`, `subtitle`, `page_icon`, `layout`, `version`                                                                                                                             | Welcome-page header and Streamlit page setup |
| `database` | `db_schema`, `connect_timeout`, `pool_size`, `max_overflow`, `pool_recycle_seconds`, `max_rows`, `statement_timeout_ms`, `cache_ttl_seconds`, `cache_max_entries`                    | Schema, connection pool and query/cache limits |

The provider enforces TLS (`sslmode=require`) and disables psycopg's prepared-statement
cache (`prepare_threshold=None`). The Supabase transaction pooler multiplexes clients
over one server connection, so cached statements can otherwise collide across clients.

### Theme

`.streamlit/config.toml` uses Streamlit's dark base with slate backgrounds, light text,
teal links and a six-colour chart palette. The contrast ratios for body text, muted
labels, links and chart lines are all above the WCAG AA threshold on the
`#0f172a` background. Plotly figures use transparent backgrounds, light axis/title
text, subtle light gridlines, dark hover cards and a bright categorical palette so
the charts stay readable in the dark theme.

## Performance

Direct Postgres is the fastest path for this dashboard, but only if the heavy work
stays in the database. The provider applies these guardrails:

- **Views-only contract** — page queries target views in the `geo` schema; GEO_ETL's
  base and `_etl` tables are never read directly by the app.
- **Row cap** — `read_dataframe()` wraps the query with `LIMIT max_rows + 1` and raises
  `QueryTooLargeError` instead of pulling an entire result set into Streamlit.
- **Statement timeout** — every query runs with `SET LOCAL statement_timeout`, so a
  slow query cannot hold a pooled connection indefinitely.
- **Bounded cache** — `cached_query()` uses `st.cache_data` with a TTL and a maximum
  number of entries; cache aggregated, chart-sized results only.
- **Pool hygiene** — `pool_pre_ping` and `pool_recycle` handle pooler restarts and
  idle connection reaping.

For the full decision matrix (direct Postgres vs GEO_API vs Supabase REST), query
rules, indexing advice and the read-only role SQL, see
[Performance](docs/performance.md).

## Development

```bash
conda activate geo_visual_311

ruff check .           # lint
ruff format --check .  # format check (tox -e format-fix to apply)
mypy                   # type check
pytest                 # tests
```

### Tox environments

Run the same checks in isolated virtualenvs:

```bash
tox                    # lint + py311 (default envlist)
tox -e lint            # ruff check
tox -e format          # ruff format --check
tox -e format-fix      # ruff format (writes the changes)
tox -e typecheck       # mypy
tox -e py311           # full pytest suite
tox -e warnings        # tests with DeprecationWarning treated as an error
```

Tox stores its virtualenvs in `~/.cache/tox/geo_visual` (configured with `work_dir`
in `tox.ini`). Keeping them outside the repository matters for Streamlit: its
watchdog watches the app folder recursively, and a local `.tox` with tens of
thousands of files overflows the Linux inotify queue.

## Testing

The suite is unit-focused: database calls are mocked, so no live Supabase connection
or network access is required. `test/test_app.py` renders the real `app.py` through
Streamlit's `AppTest` and checks the welcome page and every collapsible
dashboard/map card; `test/test_metrics_pages.py` parametrizes all eight
natural-phenomenon pages and checks their timelines, histograms, KPIs, empty
states and friendly error cards. `test/test_phenomenon_map.py` parametrizes all
nine area maps and covers metadata/category discovery, per-area SQL formatting,
query filters, full country/region names, per-phenomenon size ranges, text
colour scales, structured tooltip formatting, percentile/danger filtering,
summary cards, the emoji size legend, map frames and projections, dateline
wrapping, hover text and page controls.
`test/dashboard/test_metrics_timeline.py` covers the shared engine,
timeline/histogram builders and aggregation cases;
`test/dashboard/test_dashboard_configs.py` parametrizes the eight dashboard
configurations and their timeline/distribution SQL loading. Provider tests cover
the row cap, statement timeout, scalar queries and engine options;
`test/test_database.py` covers the cached query wrapper.

```bash
pytest                 # full suite
pytest test/dashboard  # one area
pytest -q              # quiet
```

`test/conftest.py` removes ambient `SUPABASE_DB_*` variables and points the config at a
nonexistent `.env`, so a developer's local credentials can never leak into a test run.

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
