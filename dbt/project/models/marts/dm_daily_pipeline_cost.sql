-- dm_daily_pipeline_cost
-- Günlük pipeline maliyet özeti.
-- Optimizasyon öncesi/sonrası karşılaştırması.

{{ config(
    partition_by={
        "field": "run_date",
        "data_type": "date",
        "granularity": "day"
    }
) }}

WITH cost_data AS (
    SELECT * FROM {{ ref('fct_model_cost') }}
),

daily AS (
    SELECT
        run_date,
        COUNT(DISTINCT job_id) AS total_jobs,
        COUNT(DISTINCT model_name) AS model_count,
        SUM(bytes_processed) AS total_bytes_processed,
        SUM(shadow_cost_usd) AS total_shadow_cost_usd,
        ROUND(AVG(shadow_cost_usd), 10) AS avg_cost_per_model,
        ROUND(
            SUM(shadow_cost_usd) / NULLIF(COUNT(DISTINCT model_name), 0), 10
        ) AS cost_per_model_avg,
        CURRENT_TIMESTAMP() AS processed_at
    FROM cost_data
    GROUP BY run_date
)

SELECT * FROM daily
