# Performance and data-access architecture

## Decision: direct Supabase Postgres

GEO_Visual reads directly from Supabase Postgres through the connection pooler.
For an analytical dashboard this is the lowest-latency option: one network hop,
no API/JSON serialization, and full SQL — aggregations, window functions and
PostGIS — runs next to the data.

The app queries **views** in the `geo` schema, never GEO_ETL's base or `_etl`
tables. Views are the dashboard's stable data contract: GEO_ETL can change the
tables and ETL internals behind them without breaking page queries.

In the GEO_E2E Compose stack the same provider runs inside the `geo_streamlit`
image; its entrypoint writes `.env` from the Compose environment at startup.

| Path | Hops | Strengths | Costs | Best for |
|------|------|-----------|-------|----------|
| **Direct Postgres** (chosen) | Streamlit → Supabase pooler → Postgres | One hop, full SQL, fast aggregation, no endpoint maintenance | DB credentials live in the app; heavy queries consume database resources | Internal analytical dashboards |
| **GEO_API** (FastAPI) | Streamlit → FastAPI → Supabase | Central auth/rate limiting, shared caching, no DB credentials in the app | Extra hop, JSON serialization, an endpoint for every new view | Public or multi-consumer access, strict service decoupling |
| **Supabase REST / PostgREST** | Streamlit → PostgREST → Postgres | Anon key + RLS, no SQL driver | Row limits and pagination, limited analytical SQL, more round trips | Simple CRUD and small queries |

### Why not route through GEO_API?

GEO_API is the right public interface, but it would add a second network hop and
a JSON encode/decode cycle to every dashboard interaction. It currently exposes
purpose-built endpoints; arbitrary analytical queries would require either many
new endpoints or a generic query endpoint that is harder to secure. For a
single internal dashboard, direct read-only SQL is simpler and faster.

Use GEO_API instead when GEO_Visual becomes a public/multi-tenant product, when
the database must not be reachable from the dashboard host, or when a shared
server-side cache across many consumers is required.

### Why not Supabase REST (PostgREST)?

PostgREST is excellent for CRUD and small filtered queries. Analytical
dashboards need `GROUP BY`, CTEs, window functions, percentiles and PostGIS
operations; expressing those through REST is awkward and often means pulling
more rows than necessary. The direct Postgres path keeps the computation in the
database.

## Applied guardrails

The provider in `provider/supabase_postgres/supabase_postgres_provider.py`
enforces these limits on every dataframe query:

| Guardrail | Default | Where |
|-----------|---------|-------|
| Row cap per query | `50 000` | `database.max_rows` in `config.json` |
| Distribution query cap | `250 000` | `database.distribution_max_rows` in `config.json` |
| Area map POI cap | `50 000` | `database.map_max_rows` in `config.json` |
| PostgreSQL statement timeout | `30 000 ms` | `database.statement_timeout_ms` |
| Result cache TTL | `300 s` | `database.cache_ttl_seconds` |
| Result cache entries | `32` | `database.cache_max_entries` |
| Connection-status cache TTL | `60 s` | `database.connection_status_ttl_seconds` |
| Pool size / overflow | `5` / `5` | `database.pool_size` / `max_overflow` |
| Pool recycle | `300 s` | `database.pool_recycle_seconds` |

- **Views-only contract** — page queries target views in the `geo` schema; base
  and `_etl` tables are owned by GEO_ETL and are not read by the app.
- **Distribution cap** — the histogram query selects only
  `metric_name`, `metric_unit` and `metric_value`, and uses a dedicated
  `250 000`-row cap so the raw-value payload stays bounded.
- **Map POI cap** — each area map query deduplicates events in SQL, filters by
  `event_start_date` in the database and is capped at `50 000` POIs. The date
  and category picker metadata comes from a separate one-row aggregate query per
  area view.
- `read_dataframe()` wraps the query in
  `SELECT * FROM (<query>) AS geo_visual_query LIMIT max_rows + 1` and raises
  `QueryTooLargeError` if the extra row exists. The full result never enters the
  Streamlit process.
- Each query runs inside a transaction with
  `SET LOCAL statement_timeout = <ms>`, so a slow query cannot hold a pool
  connection indefinitely.
- `cached_query()` in `utils/database.py` wraps the provider with
  `st.cache_data(ttl=..., max_entries=...)`. Cache only bounded results: the
  timeline aggregates and the capped distribution values for the selected range.
- The engine uses `pool_pre_ping` and `pool_recycle` to survive pooler restarts
  and idle connection reaping.
- Prepared statements are disabled (`prepare_threshold=None`) because the
  Supabase transaction pooler multiplexes clients over one server connection.

## Query rules for dashboard pages

1. **Query views only.** Use `geo.<dashboard_view>`; never read base or `_etl`
   tables directly. Views are the app's stable contract and hide ETL internals.
2. **Aggregate in SQL.** A daily trend chart needs `GROUP BY date`, not every
   event row. A source summary needs `COUNT(*)`, not a full view.
3. **Select only the columns you use.** Avoid `SELECT *` in page queries.
4. **Filter in SQL.** Use `WHERE file_date = :date`, `source_name = :source`,
   bounding boxes for maps, and `LIMIT` for previews.
5. **Use the cache for repeated work.** Call `cached_query()` with hashable
   parameters; keep the result small.
6. **Paginate large views.** Fetch one page with `LIMIT/OFFSET` and show a page
   control instead of loading the whole view into `st.dataframe`.
7. **Aggregate before charting.** Large Plotly traces and thousands of map
   points are slow in the browser even if the database returns them quickly.
8. **Add indexes for real filters.** `file_date`, `source_name`, event date and
   geometry columns are the usual candidates.
9. **Materialize expensive repeated aggregates.** If a view is queried on every
   page load and changes only after an ETL run, create a materialized view in
   Supabase and refresh it at the end of the ETL job.

## Read-only database role

The dashboard only needs `SELECT` on the views it exposes. Create a dedicated
read-only role instead of using the `postgres` superuser, and put those
credentials in `.env`:

```sql
CREATE ROLE geo_visual_reader LOGIN PASSWORD '<strong-password>';
GRANT USAGE ON SCHEMA geo TO geo_visual_reader;
GRANT SELECT ON geo.<dashboard_view> TO geo_visual_reader;
```

Repeat the `GRANT SELECT` for every view the dashboard uses. Do not grant
`SELECT` on the base or `_etl` tables; the views are the only interface the app
should have. If the project uses Row Level Security, add policies for this role
rather than granting `BYPASSRLS`.

## When to move to GEO_API

Switch the data layer to GEO_API if any of these become true:

- The dashboard is exposed to users who must not hold database credentials.
- Multiple applications need the same cached aggregates.
- Central rate limiting, audit logging or authorization is required.
- The database network is closed to application hosts.
- A shared cache must survive Streamlit restarts and scale across replicas.

The `cached_query()` boundary keeps this migration small: replace its
implementation with an API client while page code keeps the same signature.
