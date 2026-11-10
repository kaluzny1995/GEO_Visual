-- First and last event start date for the US phenomenon map date picker.
-- No bind parameters: the view holds every phenomenon.
SELECT to_char(min(event_start_date), 'YYYY-MM-DD') AS min_date,
       to_char(max(event_start_date), 'YYYY-MM-DD') AS max_date
FROM geo.phenomenons_us_vw
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND event_start_date IS NOT NULL;
