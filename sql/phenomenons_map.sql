-- One map point per natural-phenomenon event in one area view.
-- The {view_name} placeholder is filled from the map configuration.
-- Bind parameters:
--   :min_magnitude  minimum earthquake magnitude to include
--   :start_date     first event start date to include (inclusive)
--   :end_date       last event start date to include (inclusive)
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
