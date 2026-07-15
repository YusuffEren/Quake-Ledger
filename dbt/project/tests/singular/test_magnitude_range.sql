-- Veri kalitesi: Büyüklük değerleri -2 ile 10 arasında olmalı
-- Bu test fail ederse, kaynak API'den anormal veri geliyor demektir

WITH invalid AS (
    SELECT earthquake_id, source, mag, event_time
    FROM {{ ref('stg_usgs_earthquakes') }}
    WHERE mag IS NOT NULL AND (mag < -2 OR mag > 10)
    UNION ALL
    SELECT earthquake_id, source, mag, event_time
    FROM {{ ref('stg_kandilli_earthquakes') }}
    WHERE mag IS NOT NULL AND (mag < -2 OR mag > 10)
)

SELECT 'Magnitude range check' AS test_name,
       COUNT(*) AS invalid_count
FROM invalid
WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
HAVING COUNT(*) > 0
