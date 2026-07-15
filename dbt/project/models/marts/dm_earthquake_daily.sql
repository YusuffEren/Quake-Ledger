-- dm_earthquake_daily
-- Günlük deprem özet istatistikleri.
-- Partition: event_date, Cluster: source
-- Incremental: her çalıştırmada sadece son 3 günü yeniden hesaplar.

{{ config(
    partition_by={
        "field": "event_date",
        "data_type": "date",
        "granularity": "day"
    },
    cluster_by=["source"],
    materialized='incremental',
    incremental_strategy='insert_overwrite'
) }}

{% if is_incremental() %}
  {% set max_date = "DATE(MAX(event_time)) FROM " ~ ref('stg_usgs_earthquakes') %}
{% endif %}

WITH source_usgs AS (
    SELECT
        DATE(event_time) AS event_date,
        'usgs' AS source,
        mag AS magnitude,
        earthquake_id AS event_id
    FROM {{ ref('stg_usgs_earthquakes') }}
    {% if is_incremental() %}
    WHERE DATE(event_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
    {% endif %}
),

source_emsc AS (
    SELECT
        DATE(event_time) AS event_date,
        'emsc' AS source,
        mag AS magnitude,
        earthquake_id AS event_id
    FROM {{ ref('stg_emsc_earthquakes') }}
),

source_kandilli AS (
    SELECT
        DATE(event_time) AS event_date,
        'kandilli' AS source,
        mag AS magnitude,
        earthquake_id AS event_id
    FROM {{ ref('stg_kandilli_earthquakes') }}
),

all_sources AS (
    SELECT * FROM source_usgs
    UNION ALL
    SELECT * FROM source_emsc
    UNION ALL
    SELECT * FROM source_kandilli
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
