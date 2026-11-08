-- First and last snapshot date for the volcano metrics timeline date picker.
-- No bind parameters: the view holds one event category only.
SELECT to_char(min(file_date), 'YYYY-MM-DD') AS min_date,
       to_char(max(file_date), 'YYYY-MM-DD') AS max_date
FROM geo.metrics_volcano_vw;
