-- Minimum event sayısı: Son 6 saatte en az 1 USGS event'i olmalı
-- (Deprem fırtınası olmasa bile dünyada sürekli deprem olur)

WITH hourly AS (
    SELECT
        TIMESTAMP_TRUNC(event_time, HOUR) AS hour_bucket,
        COUNT(*) AS event_count
    FROM `deprem-502519`.`raw`.`usgs_earthquakes`
    WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 6 HOUR)
    GROUP BY 1
)

SELECT 'Min events check' AS test_name,
       COUNT(*) AS hours_with_events,
       COALESCE(SUM(event_count), 0) AS total_events
FROM hourly
HAVING COUNT(*) < 2  -- En az 2 saat diliminde event olmalı