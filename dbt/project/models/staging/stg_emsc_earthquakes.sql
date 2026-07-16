-- stg_emsc_earthquakes
-- EMSC ham verisini normalize eder, ortak şemaya dönüştürür.
-- EMSC, USGS ile aynı FDSN GeoJSON formatını kullanır — şema neredeyse birebir.
-- Kaynak: raw.emsc_earthquakes

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'emsc_earthquakes') }}
),

dedup AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY event_id
            ORDER BY ingestion_time DESC, updated DESC NULLS LAST
        ) AS rn
    FROM source
),

normalized AS (
    SELECT
        event_id AS earthquake_id,
        'emsc' AS `source`,
        event_time,
        mag,
        depth_km,
        lon,
        lat,
        place,
        updated AS source_updated_at,
        ingestion_time,
        raw_json,

        -- EMSC'e özgü alanlar
        mag_type,
        source_url

    FROM dedup
    WHERE rn = 1
)

SELECT * FROM normalized
