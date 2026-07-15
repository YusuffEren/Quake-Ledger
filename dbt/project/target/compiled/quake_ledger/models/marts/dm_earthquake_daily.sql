-- dm_earthquake_daily
-- Günlük deprem özet istatistikleri.
-- Partition: event_date
-- Cluster: source



WITH source_usgs AS (
    SELECT
        DATE(event_time) AS event_date,
        'usgs' AS source,
        mag AS magnitude,
        earthquake_id AS event_id
    FROM `deprem-502519`.`staging`.`stg_usgs_earthquakes`
),

-- Kandilli source (şu an veri yok, veri geldiğinde aktif edilecek)
-- source_kandilli AS (
--     SELECT
--         DATE(event_time) AS event_date,
--         'kandilli' AS source,
--         mag AS magnitude,
--         earthquake_id AS event_id
--     FROM `deprem-502519`.`staging`.`stg_kandilli_earthquakes`
-- ),

all_sources AS (
    SELECT * FROM source_usgs
    -- UNION ALL
    -- SELECT * FROM source_kandilli
),

aggregated AS (
    SELECT
        event_date,
        source,
        COUNT(DISTINCT event_id) AS earthquake_count,
        ROUND(AVG(magnitude), 2) AS avg_magnitude,
        ROUND(MAX(magnitude), 2) AS max_magnitude,
        ROUND(MIN(magnitude), 2) AS min_magnitude,
        CURRENT_TIMESTAMP() AS processed_at
    FROM all_sources
    WHERE magnitude IS NOT NULL
    GROUP BY event_date, source
)

SELECT * FROM aggregated