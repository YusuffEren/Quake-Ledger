-- fct_unified_earthquakes
-- Birleştirilmiş deprem olayları.
-- Eşleşen kayıtlar tek satırda birleştirilir, canonical source seçimi yapılır.
-- Anlaşmazlık metrikleri (disagreement) hesaplanır.

WITH matches AS (
    SELECT * FROM {{ ref('int_earthquake_matches') }}
),

unified AS (
    SELECT
        -- Unified ID — eşleşme varsa USGS ID kullan, yoksa mevcut ID
        match_status,

        usgs_id,
        kandilli_id,
        usgs_mag,

        -- Canonical zaman (USGS öncelikli)
        kandilli_mag,

        -- Canonical koordinat (USGS öncelikli, Türkiye'de Kandilli)
        usgs_place,
        kandilli_place,

        -- Canonical büyüklük (USGS baz alınır, Türkiye'de Kandilli tercih)
        CASE
            WHEN match_status = 'matched'
                THEN
                    CASE
                    -- Türkiye depremleri için Kandilli ID
                        WHEN
                            COALESCE(kandilli_lat, usgs_lat) BETWEEN 35 AND 43
                            AND COALESCE(
                                kandilli_lon, usgs_lon
                            ) BETWEEN 25 AND 46
                            THEN
                                CONCAT(
                                    'unified_', COALESCE(kandilli_id, usgs_id)
                                )
                        ELSE CONCAT('unified_', COALESCE(usgs_id, kandilli_id))
                    END
            WHEN match_status = 'usgs_only' THEN CONCAT('unified_', usgs_id)
            WHEN
                match_status = 'kandilli_only'
                THEN CONCAT('unified_', kandilli_id)
        END AS unified_id,

        -- Kaynak değerleri
        COALESCE(usgs_time, kandilli_time) AS event_time,
        CASE
            WHEN
                COALESCE(kandilli_lat, usgs_lat) BETWEEN 35 AND 43
                AND COALESCE(kandilli_lon, usgs_lon) BETWEEN 25 AND 46
                THEN COALESCE(kandilli_lat, usgs_lat)
            ELSE COALESCE(usgs_lat, kandilli_lat)
        END AS canonical_lat,
        CASE
            WHEN
                COALESCE(kandilli_lat, usgs_lat) BETWEEN 35 AND 43
                AND COALESCE(kandilli_lon, usgs_lon) BETWEEN 25 AND 46
                THEN COALESCE(kandilli_lon, usgs_lon)
            ELSE COALESCE(usgs_lon, kandilli_lon)
        END AS canonical_lon,
        CASE
            WHEN
                match_status = 'matched'
                AND COALESCE(kandilli_lat, usgs_lat) BETWEEN 35 AND 43
                AND COALESCE(kandilli_lon, usgs_lon) BETWEEN 25 AND 46
                THEN COALESCE(kandilli_mag, usgs_mag)
            ELSE COALESCE(usgs_mag, kandilli_mag)
        END AS canonical_mag,

        -- Anlaşmazlık metrikleri
        CASE
            WHEN usgs_mag IS NOT NULL AND kandilli_mag IS NOT NULL
                THEN ROUND(ABS(usgs_mag - kandilli_mag), 2)
        END AS mag_disagreement,

        CASE
            WHEN usgs_time IS NOT NULL AND kandilli_time IS NOT NULL
                THEN time_diff_seconds
        END AS time_diff_seconds,

        CASE
            WHEN
                usgs_lat IS NOT NULL AND kandilli_lat IS NOT NULL
                AND usgs_lon IS NOT NULL AND kandilli_lon IS NOT NULL
                THEN ROUND(distance_km, 1)
        END AS distance_km,

        -- Zaman bazlı metrikler
        CASE
            WHEN match_status = 'matched' THEN 'both'
            WHEN match_status = 'usgs_only' THEN 'usgs'
            WHEN match_status = 'kandilli_only' THEN 'kandilli'
        END AS sources_available,

        CURRENT_TIMESTAMP() AS processed_at

    FROM matches
)

SELECT * FROM unified
