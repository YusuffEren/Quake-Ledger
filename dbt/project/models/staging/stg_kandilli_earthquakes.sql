-- stg_kandilli_earthquakes
-- Kandilli ham verisini normalize eder, ortak şemaya dönüştürür.
-- Kaynak: raw.kandilli_earthquakes

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'kandilli_earthquakes') }}
),

dedup AS (
    -- Aynı earthquake_id için en son ingestion'ı al
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY earthquake_id
            ORDER BY ingestion_time DESC, created_at DESC NULLS LAST
        ) AS rn
    FROM source
),

normalized AS (
    SELECT
        -- Ortak alanlar
        earthquake_id,
        'kandilli' AS `source`,
        date_time AS event_time,
        mag,
        depth_km,
        lon,
        lat,
        title AS place,
        created_at AS source_updated_at,
        ingestion_time,
        raw_json,

        -- Kandilli'ye özgü alanlar
        location_tz,
        provider,
        epi_center_name,
        epi_center_population,
        closest_city_name,
        closest_city_distance_km,
        location_properties

    FROM dedup
    WHERE rn = 1
)

SELECT * FROM normalized
