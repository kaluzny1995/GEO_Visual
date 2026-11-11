-- First and last event start date plus the available categories for one map.
-- The {view_name} placeholder is filled from the map configuration.
-- No bind parameters.
SELECT to_char(min(event_start_date), 'YYYY-MM-DD') AS min_date,
       to_char(max(event_start_date), 'YYYY-MM-DD') AS max_date,
       array_agg(DISTINCT event_category ORDER BY event_category) AS categories
FROM {view_name}
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND event_start_date IS NOT NULL;
