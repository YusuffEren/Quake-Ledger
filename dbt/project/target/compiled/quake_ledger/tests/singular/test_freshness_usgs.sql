-- Freshness SLA: En son USGS depremi 30 dakikadan eskiyse uyarı, 120dkdan eskiyse fail
-- Ingestion çalışıyor mu kontrolü

WITH latest AS (
    SELECT MAX(event_time) AS latest_event_time
    FROM `deprem-502519`.`raw`.`usgs_earthquakes`
    WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
)

SELECT 'USGS freshness check' AS test_name,
       latest_event_time,
       TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), latest_event_time, MINUTE) AS minutes_since_last_event
FROM latest
WHERE latest_event_time IS NULL
   OR latest_event_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 120 MINUTE)