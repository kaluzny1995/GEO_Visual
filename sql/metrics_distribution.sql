-- Raw metric values for the distribution histograms.
-- The {view_name} placeholder is filled from the dashboard configuration.
-- Bind parameters:
--   :start_date  first snapshot date to include (inclusive)
--   :end_date    last snapshot date to include (inclusive)
SELECT metric_name,
       metric_unit,
       is_predicted,
       metric_value
FROM {view_name}
WHERE file_date >= CAST(:start_date AS date)
  AND file_date < CAST(:end_date AS date) + INTERVAL '1 day'
ORDER BY metric_name, metric_unit, is_predicted;
