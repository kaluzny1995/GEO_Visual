# Drought metrics timeline

The drought dashboard follows daily drought metrics from the
`geo.metrics_drought_vw` view. Every distinct metric gets its own linear
timeline, using the same shared engine as the
[Avalanche metrics timeline](avalanche-timeline.md) and
[Earthquake metrics timeline](earthquake-timeline.md).

Open it at **<http://localhost:8501> → Drought Timeline**, from the dashboard
card on the welcome page, or via `pages/2_Drought_Timeline.py` in the source
tree.

## Data source

`geo.metrics_drought_vw` is written by GEO_ETL from the drought rows of
`geo.union_etl`. It unpivots each row into one metric observation:

| Column              | Meaning                                              |
|---------------------|------------------------------------------------------|
| `event_category`    | Always `drought` in this view                        |
| `event_subcategory` | The source subtype                                   |
| `metric_name`       | `area` or another numeric drought metric             |
| `metric_value`      | Numeric observation                                  |
| `metric_unit`       | Unit paired with the metric (`km²` for drought area) |
| `file_date`         | Daily snapshot date                                  |

Today the view publishes drought `area` in `km²` from GDACS. The view is ready
for additional numeric drought metrics if another source starts sending them;
a new metric appears automatically as a new chart.

Each `file_date` is one snapshot. The dashboard aggregates in PostgreSQL and
sends only one row per `(file_date, metric_name, metric_unit)` to Streamlit.

## Aggregation

The **Statistic** selector changes the y-axis and is applied to every metric:

| Statistic      | SQL aggregate                                                | Meaning |
|----------------|--------------------------------------------------------------|---------|
| `Mean`         | `avg(metric_value)`                                          | Average recorded value across events in the snapshot |
| `Median`       | `percentile_cont(0.5) WITHIN GROUP (ORDER BY metric_value)`  | Median recorded value in the snapshot |
| `Maximum`      | `max(metric_value)`                                          | Highest recorded value in the snapshot |
| `Total`        | `sum(metric_value)`                                          | Sum of recorded values in the snapshot |
| `Observations` | `count(*)`                                                   | Number of rows recorded for the metric |

All statistics aggregate every recorded value. The `Mean` view also draws a
translucent observed min-max band across the events in each snapshot.

Every chart spans the selected date range. Periods where a metric has no
observations are shaded instead of being cut out or connected with a straight line,
with their ranges listed in a compact caption below the chart. Drought snapshots are not published every
day, so gap shading is expected.

## Query

The dashboard runs two guarded queries through
`utils.database.cached_query()`. Both live in the `sql/` folder and are loaded
by `utils.sql.load_sql()`:

| File | Purpose |
|------|---------|
| `sql/drought_metrics_date_bounds.sql` | Date picker bounds; no bind parameters |
| `sql/drought_metrics_timeline.sql` | Timeline aggregates; binds `:start_date` and `:end_date` |

```sql
-- sql/drought_metrics_date_bounds.sql
SELECT to_char(min(file_date), 'YYYY-MM-DD') AS min_date,
       to_char(max(file_date), 'YYYY-MM-DD') AS max_date
FROM geo.metrics_drought_vw;

-- sql/drought_metrics_timeline.sql
SELECT file_date::date AS file_date,
       metric_name,
       metric_unit,
       count(*) AS observation_count,
       avg(metric_value) AS mean_value,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY metric_value) AS median_value,
       max(metric_value) AS max_value,
       min(metric_value) AS min_value,
       sum(metric_value) AS sum_value
FROM geo.metrics_drought_vw
WHERE event_category = 'drought'
  AND file_date >= CAST(:start_date AS date)
  AND file_date < CAST(:end_date AS date) + INTERVAL '1 day'
GROUP BY file_date, metric_name, metric_unit
ORDER BY file_date, metric_name, metric_unit;
```

Both queries are bounded chart-sized results and are cached by
`cached_query()` for `database.cache_ttl_seconds` (300 seconds by default).
The page follows the [views-only contract](performance.md): it never reads
GEO_ETL's base or `_etl` tables.

## Page behaviour

- **Snapshot range** — defaults to the full range in the view; the start and
  end dates are inclusive.
- **One chart per metric** — metrics are discovered from the returned rows, so
  a new numeric metric in the view appears without a code change.
- **All recorded values** — every chart spans the selected date range; periods
  where a metric has no observations are shaded, with their ranges listed below the chart; the grey field reaches the nearest observed snapshot on each side.
- **KPIs** — snapshots, metrics, observations and the latest snapshot in the
  selected range.
- **Aggregated data** — an expander shows the query result and offers a CSV
  download.
- **Empty and error states** — a missing view, unconfigured Supabase or an
  empty date range produces a short message instead of a stack trace.

## Code map

| File | Role |
|------|------|
| `pages/2_Drought_Timeline.py` | Streamlit page entry — page config, shared sidebar, render call |
| `dashboard/drought_timeline.py` | Drought `DashboardConfig` (view, title, SQL) |
| `dashboard/metrics_timeline.py` | Shared timeline engine, aggregation metadata, metric grouping and Plotly figures |
| `dashboard/catalog.py` | Dashboard metadata for the welcome cards and sidebar navigation |
| `sql/drought_metrics_date_bounds.sql` | Date picker bounds query |
| `sql/drought_metrics_timeline.sql` | Parametrized timeline aggregate query |
| `utils/sql.py` | Loads the checked-in `.sql` scripts |
| `utils/layout.py` | Shared page configuration, custom Start + collapsible Metric timelines sidebar nav (branding + Supabase status) |
| `test/dashboard/test_metrics_timeline.py` | Shared engine, aggregation, figure, gap and band tests |
| `test/dashboard/test_dashboard_configs.py` | Parametrized avalanche/drought/earthquake configuration and query tests |
| `test/test_metrics_pages.py` | Parametrized page rendering, KPIs, empty states and error cards via `AppTest` |
| `test/test_sql.py` | SQL file contents, bind parameters and loader behavior |

## Testing

The drought page is covered by the same parametrized suites as the avalanche
page: configuration and SQL loading, chart builders, page rendering with
patched data, empty states and error cards. No live Supabase connection is
required.

```bash
pytest test/dashboard test/test_metrics_pages.py test/test_sql.py
```
