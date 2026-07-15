-- Çapraz kaynak anlaşmazlık testi:
-- USGS ile Kandilli arasında büyüklük farkı > 2.0 ise uyarı
-- Bu, kaynaklardan birinin anormal okuma yaptığını gösterebilir

WITH disagreement AS (
    SELECT
        unified_id,
        usgs_mag,
        kandilli_mag,
        mag_disagreement,
        event_time,
        usgs_place,
        kandilli_place
    FROM {{ ref('fct_unified_earthquakes') }}
    WHERE match_status = 'matched'
      AND mag_disagreement > 2.0
      AND event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
)

SELECT 'Cross-source large disagreement' AS test_name,
       COUNT(*) AS disagreement_count,
       ARRAY_AGG(
           STRUCT(unified_id, usgs_mag, kandilli_mag, mag_disagreement)
           ORDER BY mag_disagreement DESC
           LIMIT 5
       ) AS top_disagreements
FROM disagreement
HAVING COUNT(*) > 0
