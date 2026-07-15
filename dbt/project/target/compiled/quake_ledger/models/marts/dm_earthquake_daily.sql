-- dm_earthquake_daily
-- Günlük deprem özet istatistikleri.
-- Partition: event_date
-- Cluster: source



WITH source_unified AS (
    SELECT
        DATE(event_time) AS event_date,
        'unified' AS source,
        canonical_mag AS magnitude,
        unified_id AS event_id
    FROM `deprem-502519`.`staging`.`fct_unified_earthquakes`

    UNION ALL

    SELECT
        DATE(event_time) AS event_date,
        source,
        mag AS magnitude,
        earthquake_id AS event_id
    FROM `deprem-502519`.`staging`.`stg_usgs_earthquakes`

    UNION ALL

    SELECT
        DATE(event_time) AS event_date,
        source,
        mag AS magnitude,
        earthquake_id AS event_id
    FROM `deprem-502519`.`staging`.`stg_kandilli_earthquakes`
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
    FROM source_unified
    WHERE magnitude IS NOT NULL
    GROUP BY event_date, source
)

SELECT * FROM aggregated
ORDER BY event_date DESC, source