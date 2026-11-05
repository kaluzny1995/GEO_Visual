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

The repository currently ships a minimal welcome page (title and description)
with a compact left sidebar for branding and Supabase connection status. Supabase
connection helpers and performance guardrails are ready for the upcoming data
exploration, mapping and data-quality pages.

GEO_Visual reads directly from Supabase Postgres rather than routing analytical
queries through GEO_API: one network hop, full SQL pushdown and no JSON
serialization. The app queries views in the `geo` schema only — base and `_etl`
tables remain owned by GEO_ETL. See [Performance](docs/performance.md) for the
trade-offs and the guardrails that keep large result sets out of the Streamlit process.

> Status: welcome page and Supabase connectivity are in place; dashboard pages are planned.

## Features

- **Streamlit welcome page** — title, short description and compact left sidebar
- **Supabase connectivity** — SQLAlchemy 2.0 sync engine with the psycopg 3 driver,
  credentials from `.env`, TLS enforced and prepared statements disabled for the
  Supabase transaction pooler
- **Views-only data contract** — dashboard queries read views in the `geo` schema,
  never GEO_ETL's base or `_etl` tables
- **Connection helpers** — one pooled engine per Streamlit process (`st.cache_resource`),
  a cached connection status with a sidebar **Recheck connection** button, and a
  bounded query cache ready for dashboard pages
- **Large-data guardrails** — every query has a row cap and a PostgreSQL statement
  timeout, and `cached_query()` caches only bounded, chart-sized results
- **Typed configuration** — Pydantic models for `config.json` and `SUPABASE_DB_*`
  environment variables
- **Themed UI** — shared Streamlit theme in `.streamlit/config.toml`
- **Dev tooling** — ruff (lint + format), mypy, pytest and tox
- **Tests without a database** — mocked engine and Streamlit's `AppTest` cover the
  welcome page and data layer

## Tech Stack

| Component        | Technology                                  |
|------------------|---------------------------------------------|
| Language         | Python 3.11                                 |
| UI framework     | Streamlit >= 1.37                           |
| Dataframes       | pandas >= 2.0                               |
| Data access      | Direct PostgreSQL (Supabase) views, read-only role recommended |
| Database         | PostgreSQL (Supabase) via SQLAlchemy 2.0    |
| DB driver        | psycopg 3 (`psycopg[binary] >= 3.1`)        |
| Configuration    | Pydantic >= 2.0, python-dotenv >= 1.0       |
| Charting         | Plotly >= 5.20 (for upcoming dashboard pages) |
| Testing          | pytest >= 7.0, Streamlit `AppTest`          |
| Lint / format    | ruff >= 0.6                                 |
| Type checking    | mypy >= 1.10                                |
| Check runner     | tox >= 4.0                                  |
| Environment      | Conda — `geo_visual_311`                    |

## Project Structure

```text
GEO_Visual/
├── app.py                                  # Streamlit entry point and welcome page
├── config.json                             # App metadata and database pool/query limits
├── error.py                                # QueryTooLargeError
├── .streamlit/
│   └── config.toml                         # Shared Streamlit theme
├── docs/
│   └── performance.md                      # Direct-Postgres rationale and views-only query rules
├── model/
│   └── config/
│       ├── app_config.py                   # config.json model
│       └── supabase_config.py              # SUPABASE_DB_* model and connection URL
├── provider/
│   └── supabase_postgres/
│       └── supabase_postgres_provider.py   # Pooled engine, guarded queries and schema introspection
├── utils/
│   └── database.py                         # Cached provider, status and cached_query()
├── test/
│   ├── model/config/                       # Config parsing and env loading
│   ├── provider/supabase_postgres/         # Provider behavior with a mocked engine
│   ├── test_app.py                         # Welcome page via Streamlit AppTest
│   ├── test_database.py                    # Connection status handling
│   └── test_project_layout.py              # Repository contract checks
├── environment.yml                         # Conda environment geo_visual_311
├── pyproject.toml                          # ruff, pytest and mypy settings
└── tox.ini                                 # Isolated lint/test/typecheck environments
```

## Prerequisites

- **Conda** — for the Python 3.11 environment
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
database; the sidebar reports if Supabase is not configured.

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
**Project → Connect → Connection pooling → Transaction pooler**.

### `config.json`

| Section    | Keys                                                                                                                                                                              | Purpose                                      |
|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| `app`      | `title`, `subtitle`, `page_icon`, `layout`, `version`                                                                                                                             | Welcome-page header and Streamlit page setup |
| `database` | `db_schema`, `connect_timeout`, `pool_size`, `max_overflow`, `pool_recycle_seconds`, `max_rows`, `statement_timeout_ms`, `cache_ttl_seconds`, `cache_max_entries`                    | Schema, connection pool and query/cache limits |

The provider enforces TLS (`sslmode=require`) and disables psycopg's prepared-statement
cache (`prepare_threshold=None`). The Supabase transaction pooler multiplexes clients
over one server connection, so cached statements can otherwise collide across clients.

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
Streamlit's `AppTest` and checks that the main area contains only the title and
description and that the sidebar exposes branding and connection status.
Provider tests cover the row cap, statement timeout, scalar queries and engine
options; `test/test_database.py` covers the cached query wrapper.

```bash
pytest                 # full suite
pytest test/model      # one area
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
  orchestration for the pipeline.
- **[GEO_APP](https://github.com/kaluzny1995/GEO_APP)** — React dashboard for the API.
