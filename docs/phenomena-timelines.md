# Fire, flood, iceberg, storm and volcano timelines

These five dashboards follow the remaining natural-phenomenon views with the
same shared `dashboard/metrics_timeline.py` engine as the
[Avalanche metrics timeline](avalanche-timeline.md),
[Drought metrics timeline](drought-timeline.md) and
[Earthquake metrics timeline](earthquake-timeline.md).

| Dashboard | Page | View | Current metric series |
|-----------|------|------|-----------------------|
| 🔥 Fire metrics timeline | `pages/4_Fire_Timeline.py` | `geo.metrics_fire_vw` | `area` (`km²`), `percent_contained` (`%`), `geometry_count` |
| 🌊 Flood metrics timeline | `pages/5_Flood_Timeline.py` | `geo.metrics_flood_vw` | `discharge` (`m³/s`), `threshold` (`m³/s`), `baseline_days`, `exceedance_ratio`, `magnitude` |
| 🧊 Iceberg metrics timeline | `pages/6_Iceberg_Timeline.py` | `geo.metrics_iceberg_vw` | `surface` (`N/m²`), `geometry_count` |
| ⛈️ Storm metrics timeline | `pages/7_Storm_Timeline.py` | `geo.metrics_storm_vw` | `speed`, `wind speed`, `gust` (`km/h`), `pressure` (`mb`), `direction` (`degrees`), `dist2land` / `landfall` (`km`), `geometry_count` |
| 🌋 Volcano metrics timeline | `pages/8_Volcano_Timeline.py` | `geo.metrics_volcano_vw` | `vei` (`VEI`), `vnum` (`Smithsonian GVP`), `casualties` (`people`), `damage` (`million USD`), `magnitude` |

Open any of them at **<http://localhost:8501>**, from the welcome-page cards,
or from the **Metric timelines** sidebar menu.

## Data shape

Each view is written by GEO_ETL from the matching `event_category` rows of
`geo.union_etl` and unpivots them into one row per
`(file_date, metric_name, metric_value, metric_unit)`. `file_date` is the daily
snapshot stamp.

Each distinct `(metric_name, metric_unit)` pair gets its own chart. A new
numeric metric in any of these views appears automatically without a page
change. Known abbreviations get readable display names (`nst` → `NST`, `vei` →
`VEI`, `vnum` → `Volcano Number`, `dist2land` → `Distance to Land`).

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
observations are shaded, with their ranges listed below the chart; the grey field reaches the nearest observed snapshot on each side. This is expected for
sparse metrics such as volcano casualties, damage or iceberg geometry counts.

## SQL files

Each dashboard has two checked-in SQL scripts loaded by `utils.sql.load_sql()`:

```text
sql/fire_metrics_date_bounds.sql       sql/fire_metrics_timeline.sql
sql/flood_metrics_date_bounds.sql      sql/flood_metrics_timeline.sql
sql/iceberg_metrics_date_bounds.sql    sql/iceberg_metrics_timeline.sql
sql/storm_metrics_date_bounds.sql      sql/storm_metrics_timeline.sql
sql/volcano_metrics_date_bounds.sql    sql/volcano_metrics_timeline.sql
```

The timeline scripts bind `:start_date` and `:end_date`; the bounds scripts
have no bind parameters. Both are bounded chart-sized queries cached by
`cached_query()` and follow the
[views-only contract](performance.md).

## Page behaviour

Every page has the same controls and layout:

- **Snapshot range** — defaults to the full range in the view; inclusive.
- **One chart per metric and unit** — metrics are discovered from the rows.
- **Missing observations** — shaded on the full selected timeline, with the grey field reaching the nearest observed snapshot on each side and the missing ranges listed below each chart.
- **KPIs** — snapshots, metric series, observations and the latest snapshot.
- **Aggregated data** — preview and CSV download.
- **Empty and error states** — short messages instead of stack traces.

## Code map

| File | Role |
|------|------|
| `pages/4_Fire_Timeline.py` … `pages/8_Volcano_Timeline.py` | Streamlit page entries |
| `dashboard/fire_timeline.py` … `dashboard/volcano_timeline.py` | Per-view `DashboardConfig` objects |
| `dashboard/metrics_timeline.py` | Shared timeline engine and Plotly figures |
| `dashboard/catalog.py` | Welcome cards and sidebar metadata |
| `utils/sql.py` | Loads the checked-in `.sql` scripts |
| `utils/layout.py` | Shared page config and collapsible **Metric timelines** navigation |
| `test/test_metrics_pages.py` | Parametrized page rendering for all eight dashboards |
| `test/dashboard/test_dashboard_configs.py` | Parametrized configuration and query tests |
| `test/test_sql.py` | SQL file contents, bind parameters and loader behavior |

## Testing

All five pages are covered by the same parametrized AppTest suite as the other
timelines, with patched data and no live Supabase connection:

```bash
pytest test/dashboard test/test_metrics_pages.py test/test_sql.py
```
