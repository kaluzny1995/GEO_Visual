-- One aggregated row per snapshot date, metric and unit.
-- Bind parameters:
--   :start_date  first snapshot date to include (inclusive)
--   :end_date    last snapshot date to include (inclusive)
SELECT file_date::date AS file_date,
       metric_name,
       metric_unit,
       count(*) AS observation_count,
       avg(metric_value) AS mean_value,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY metric_value) AS median_value,
       max(metric_value) AS max_value,
       min(metric_value) AS min_value,
       sum(metric_value) AS sum_value
FROM geo.metrics_storm_vw
WHERE event_category = 'storm'
  AND file_date >= CAST(:start_date AS date)
  AND file_date < CAST(:end_date AS date) + INTERVAL '1 day'
GROUP BY file_date, metric_name, metric_unit
ORDER BY file_date, metric_name, metric_unit;
