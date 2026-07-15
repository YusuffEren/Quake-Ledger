-- int_earthquake_matches
-- USGS ve Kandilli arasında aynı deprem eşleştirmeleri.
-- Eşikler: zaman <= 120sn, mesafe <= 50km (Haversine), büyüklük farkı <= 1.0
--
-- Haversine formülü (BigQuery SQL):
--   d = 2 * R * asin(sqrt(
--       sin((lat2-lat1)/2)^2 +
--       cos(lat1) * cos(lat2) * sin((lon2-lon1)/2)^2
--   ))
--   R = 6371 km

WITH usgs AS (
    SELECT
        earthquake_id,
        event_time,
        mag,
        lon,
        lat,
        place,
        source_updated_at
    FROM `deprem-502519`.`staging`.`stg_usgs_earthquakes`
    WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
),

kandilli AS (
    SELECT
        earthquake_id,
        event_time,
        mag,
        lon,
        lat,
        place,
        source_updated_at
    FROM `deprem-502519`.`staging`.`stg_kandilli_earthquakes`
    WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
),

-- Cross join ile tüm olası eşleşmeleri bul (son 7 gün)
candidates AS (
    SELECT
        u.earthquake_id AS usgs_id,
        k.earthquake_id AS kandilli_id,
        u.event_time AS usgs_time,
        k.event_time AS kandilli_time,
        u.mag AS usgs_mag,
        k.mag AS kandilli_mag,
        u.lon AS usgs_lon,
        u.lat AS usgs_lat,
        k.lon AS kandilli_lon,
        k.lat AS kandilli_lat,
        u.place AS usgs_place,
        k.place AS kandilli_place,

        -- Zaman farkı (saniye)
        ABS(TIMESTAMP_DIFF(u.event_time, k.event_time, SECOND)) AS time_diff_seconds,

        -- Haversine mesafesi (km)
        6371 * 2 * ASIN(SQRT(
            POW(SIN((k.lat - u.lat) * ACOS(-1) / 360), 2) +
            COS(u.lat * ACOS(-1) / 180) * COS(k.lat * ACOS(-1) / 180) *
            POW(SIN((k.lon - u.lon) * ACOS(-1) / 360), 2)
        )) AS distance_km,

        -- Büyüklük farkı
        ABS(COALESCE(u.mag, 0) - COALESCE(k.mag, 0)) AS mag_diff

    FROM usgs u
    CROSS JOIN kandilli k
    -- Zaman filtresi (performans için cross-join öncesi daraltma)
    WHERE ABS(TIMESTAMP_DIFF(u.event_time, k.event_time, SECOND)) <= 600
),

-- Eşikleri geçen eşleşmeler
matches AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY usgs_id
            ORDER BY distance_km ASC, time_diff_seconds ASC
        ) AS rn_usgs,
        ROW_NUMBER() OVER (
            PARTITION BY kandilli_id
            ORDER BY distance_km ASC, time_diff_seconds ASC
        ) AS rn_kandilli
    FROM candidates
    WHERE time_diff_seconds <= 120        -- Max 2 dakika fark
      AND distance_km <= 50              -- Max 50 km mesafe
      AND mag_diff <= 1.0                -- Max 1.0 büyüklük farkı
),

-- En iyi eşleşmeyi seç (bir USGS event'i en fazla bir Kandilli ile eşleşir)
best_matches AS (
    SELECT
        CONCAT(usgs_id, '_', kandilli_id) AS match_id,
        'matched' AS match_status,
        usgs_id,
        kandilli_id,
        usgs_time,
        kandilli_time,
        usgs_mag,
        kandilli_mag,
        usgs_lon,
        usgs_lat,
        kandilli_lon,
        kandilli_lat,
        usgs_place,
        kandilli_place,
        time_diff_seconds,
        distance_km,
        mag_diff
    FROM matches
    WHERE rn_usgs = 1 AND rn_kandilli = 1
),

-- Eşleşmeyen USGS event'leri
usgs_only AS (
    SELECT
        CONCAT(earthquake_id, '_none') AS match_id,
        'usgs_only' AS match_status,
        earthquake_id AS usgs_id,
        NULL AS kandilli_id,
        event_time AS usgs_time,
        NULL AS kandilli_time,
        mag AS usgs_mag,
        NULL AS kandilli_mag,
        lon AS usgs_lon,
        lat AS usgs_lat,
        NULL AS kandilli_lon,
        NULL AS kandilli_lat,
        place AS usgs_place,
        NULL AS kandilli_place,
        NULL AS time_diff_seconds,
        NULL AS distance_km,
        NULL AS mag_diff
    FROM usgs
    WHERE earthquake_id NOT IN (
        SELECT usgs_id FROM best_matches WHERE usgs_id IS NOT NULL
    )
),

-- Eşleşmeyen Kandilli event'leri
kandilli_only AS (
    SELECT
        CONCAT('none_', earthquake_id) AS match_id,
        'kandilli_only' AS match_status,
        NULL AS usgs_id,
        earthquake_id AS kandilli_id,
        NULL AS usgs_time,
        event_time AS kandilli_time,
        NULL AS usgs_mag,
        mag AS kandilli_mag,
        NULL AS usgs_lon,
        NULL AS usgs_lat,
        lon AS kandilli_lon,
        lat AS kandilli_lat,
        NULL AS usgs_place,
        place AS kandilli_place,
        NULL AS time_diff_seconds,
        NULL AS distance_km,
        NULL AS mag_diff
    FROM kandilli
    WHERE earthquake_id NOT IN (
        SELECT kandilli_id FROM best_matches WHERE kandilli_id IS NOT NULL
    )
),

unified AS (
    SELECT * FROM best_matches
    UNION ALL
    SELECT * FROM usgs_only
    UNION ALL
    SELECT * FROM kandilli_only
)

SELECT
    match_id,
    match_status,
    usgs_id,
    kandilli_id,
    usgs_time,
    kandilli_time,
    usgs_mag,
    kandilli_mag,
    usgs_lon,
    usgs_lat,
    kandilli_lon,
    kandilli_lat,
    usgs_place,
    kandilli_place,
    time_diff_seconds,
    distance_km,
    mag_diff
FROM unified