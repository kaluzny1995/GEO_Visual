# Avalanche metrics timeline

The first GEO_Visual dashboard follows daily avalanche metrics from the
`geo.metrics_avalanche_vw` view. Every distinct metric gets its own linear
timeline, so a change in `danger_level` is never mixed into the line for
avalanche `size` or any future metric.

Open it at **<http://localhost:8501> → Avalanche metrics timeline**, from the
dashboard card on the welcome page, or via `pages/1_Avalanche_Timeline.py` in
the source tree.

## Data source

`geo.metrics_avalanche_vw` is written by GEO_ETL from the avalanche rows of
`geo.union_etl`. It unpivots each row into one metric observation:

| Column              | Meaning                                              |
|---------------------|------------------------------------------------------|
| `event_category`    | Always `avalanche` in this view                      |
| `event_subcategory` | The source subtype (`avalanche` for this source)     |
| `metric_name`       | `danger_level`, `size` or another numeric avalanche metric |
| `metric_value`      | Numeric observation                                  |
| `metric_unit`       | Unit paired with the metric (`NAPADS level`, `destructive size class`) |
| `file_date`         | Daily snapshot date                                 |

Each `file_date` is one forecast snapshot. The view contains many rows per
snapshot (one per zone and metric), so the dashboard aggregates before
charting. Aggregation happens in PostgreSQL; only one row per
`(file_date, metric_name, metric_unit)` crosses the network.

## Aggregation

The **Statistic** selector changes the y-axis and is applied to every metric:

| Statistic    | SQL aggregate                          | Meaning |
|--------------|----------------------------------------|---------|
| `Mean`       | `avg(metric_value)`                    | Average recorded value across zones in the snapshot |
| `Median`     | `percentile_cont(0.5) WITHIN GROUP (ORDER BY metric_value)` | Median recorded value in the snapshot |
| `Maximum`    | `max(metric_value)`                    | Highest recorded value in the snapshot |
| `Total`      | `sum(metric_value)`                    | Sum of recorded values in the snapshot |
| `Observations` | `count(*)`                           | Number of rows recorded for the metric |

All four statistics use every row in the snapshot. Avalanche reports use
`danger_level = -1` for *no rating* (off-season or an unrated zone). That is an
encoded state in the source feed, not a missing measurement, so it stays in the
aggregates. Keeping it is what makes the September–October part of the timeline
visible instead of leaving a two-month gap before the first rated snapshot.

The dashboard also shows a short caption explaining the `-1` convention. Because
`-1` is an encoded state, the `Mean` of `danger_level` is a trend of the whole
feed (rated and unrated zones), not a meteorological average; `Median`,
`Maximum` and `Observations` are useful alternatives.

The `Mean` view draws a translucent observed min-max band across the zones in
each snapshot. Days without a snapshot are reindexed as gaps instead of being
connected with a straight line. When a metric has no observations for one or
more snapshots, the real timeline is still shown: the empty period is shaded
and labelled with its date range (for example, `size` before 2026-10-31).

## Query

The dashboard runs two guarded queries through
`utils.database.cached_query()`. Both live in the `sql/` folder and are loaded
by `utils.sql.load_sql()`:

| File | Purpose |
|------|---------|
| `sql/avalanche_metrics_date_bounds.sql` | Date picker bounds; no bind parameters |
| `sql/avalanche_metrics_timeline.sql` | Timeline aggregates; binds `:start_date` and `:end_date` |

```sql
-- sql/avalanche_metrics_date_bounds.sql
SELECT to_char(min(file_date), 'YYYY-MM-DD') AS min_date,
       to_char(max(file_date), 'YYYY-MM-DD') AS max_date
FROM geo.metrics_avalanche_vw;

-- sql/avalanche_metrics_timeline.sql
SELECT file_date::date AS file_date,
       metric_name,
       metric_unit,
       count(*) AS observation_count,
       avg(metric_value) AS mean_value,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY metric_value) AS median_value,
       max(metric_value) AS max_value,
       min(metric_value) AS min_value,
       sum(metric_value) AS sum_value
FROM geo.metrics_avalanche_vw
WHERE event_category = 'avalanche'
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
  a new numeric metric in the view appears without a code change. `danger_level`
  and `size` are the current avalanche metrics.
- **All recorded values** — `danger_level = -1` (no rating) is plotted as a
  real state, so the full September–November snapshot range is visible. Every
  chart spans the selected date range; periods where a metric has no
  observations are shaded and labelled with their dates. Avalanche `size`, for
  example, shows a “No size observations 2026-09-01 to 2026-10-30” band before
  its first value instead of an unexplained empty lead-in.
- **KPIs** — snapshots, metrics, observations and the latest snapshot in the
  selected range.
- **Aggregated data** — an expander shows the query result and offers a CSV
  download.
- **Empty and error states** — a missing view, unconfigured Supabase or an
  empty date range produces a short message instead of a stack trace.

## Code map

| File | Role |
|------|------|
| `pages/1_Avalanche_Timeline.py` | Streamlit page entry — page config, shared sidebar, render call |
| `dashboard/avalanche_timeline.py` | Aggregation metadata, metric grouping and Plotly figure builder |
| `sql/avalanche_metrics_date_bounds.sql` | Date picker bounds query |
| `sql/avalanche_metrics_timeline.sql` | Parametrized timeline aggregate query |
| `utils/sql.py` | Loads the checked-in `.sql` scripts |
| `utils/layout.py` | Shared page configuration, custom Start/dashboard sidebar nav (branding + Supabase status) |
| `test/dashboard/test_avalanche_timeline.py` | Parametrized aggregation, figure, gap and band tests |
| `test/test_avalanche_page.py` | Page rendering, KPIs, parametrized empty states and error card via `AppTest` |
| `test/test_sql.py` | SQL file contents, bind parameters and loader behavior |

## Testing

The dashboard is fully testable without Supabase. `AppTest` renders the real
page with `load_date_bounds` and `load_metric_timeline` patched; parametrized
chart tests cover every statistic (mean, median, maximum, total and
observations), all aggregation columns and the shared min–max band. Further
parametrized cases cover missing days, a late metric with a shaded no-data
period, an all-missing metric, empty/error page states and the SQL loader. A
query guard test prevents the `metric_value` filter that previously hid
September and October from being reintroduced.

```bash
pytest test/dashboard test/test_avalanche_page.py
```
