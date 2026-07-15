-- Freshness SLA: En son Kandilli depremi 60 dakikadan eskiyse uyarı, 240dkdan eskiyse fail

WITH latest AS (
    SELECT MAX(date_time) AS latest_event_time
    FROM `deprem-502519`.`raw`.`kandilli_earthquakes`
    WHERE date_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)
)

SELECT 'Kandilli freshness check' AS test_name,
       latest_event_time,
       TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), latest_event_time, MINUTE) AS minutes_since_last_event
FROM latest
WHERE latest_event_time IS NULL
   OR latest_event_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 120 MINUTE)