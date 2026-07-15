-- stg_usgs_earthquakes
-- USGS ham verisini normalize eder, ortak şemaya dönüştürür.
-- Kaynak: raw.usgs_earthquakes

WITH source AS (
    SELECT *
    FROM `deprem-502519`.`raw`.`usgs_earthquakes`
),

dedup AS (
    -- Aynı event_id için en son ingestion'ı al (idempotent quality)
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY event_id
            ORDER BY ingestion_time DESC, updated DESC NULLS LAST
        ) AS rn
    FROM source
),

normalized AS (
    SELECT
        -- Ortak alanlar
        event_id AS earthquake_id,
        'usgs' AS source,
        event_time,
        mag,
        depth_km,
        lon,
        lat,
        place,
        updated AS source_updated_at,
        ingestion_time,
        raw_json,

        -- USGS'e özgü alanlar
        mag_type,
        status,
        tsunami,
        sig,
        net,
        nst,
        dmin,
        rms,
        gap,
        type AS event_type,
        alert,
        cdi,
        mmi,
        felt,
        source_url

    FROM dedup
    WHERE rn = 1
)

SELECT * FROM normalized