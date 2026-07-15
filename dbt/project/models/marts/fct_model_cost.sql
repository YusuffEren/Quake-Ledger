-- fct_model_cost
-- Her dbt model çalıştırmasının maliyet metriği.
-- BigQuery INFORMATION_SCHEMA'dan okunur.
-- Gölge maliyet hesabı: $5/TiB on-demand sorgu fiyatı (US/EU multi-region)

{{ config(
    partition_by={
        "field": "run_date",
        "data_type": "date",
        "granularity": "day"
    },
    cluster_by=["model_name"]
) }}

WITH job_data AS (
    SELECT
        job_id,
        job_type,
        statement_type,
        query,
        -- Sorgunun hangi tabloya yazdığını bul (dbt model)
        REGEXP_EXTRACT(query, r'`[^`]+`\.`[^`]+`\.`([^`]+)`') AS model_name,
        destination_table,
        total_bytes_processed AS bytes_processed,
        TIMESTAMP_DIFF(end_time, start_time, SECOND) AS execution_time_seconds,
        start_time,
        end_time,
        error_result,
        cache_hit
    FROM `region-eu`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
    WHERE 1=1
      -- Sadece dbt ile ilgili job'lar
      AND (query LIKE '%staging.%' OR query LIKE '%marts.%')
      AND query NOT LIKE '%INFORMATION_SCHEMA%'
      AND query NOT LIKE '%staging_dbt_test__audit%'
      -- Son 30 gün
      AND creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      -- Başarılı job'lar
      AND error_result IS NULL
      -- Sadece SELECT ve INSERT (dbt build)
      AND statement_type IN ('SELECT', 'INSERT', 'CREATE_TABLE_AS_SELECT', 'CREATE_VIEW')
),

aggregated AS (
    SELECT
        job_id,
        COALESCE(model_name, 'unknown') AS model_name,
        job_type,
        bytes_processed,
        -- Gölge maliyet: BigQuery on-demand $5/TiB = $5/1,099,511,627,776 bytes
        ROUND(bytes_processed * 5.0 / 1099511627776, 10) AS shadow_cost_usd,
        execution_time_seconds,
        DATE(start_time) AS run_date,
        start_time,
        end_time
    FROM job_data
    WHERE bytes_processed > 0
)

SELECT
    job_id,
    model_name,
    job_type,
    bytes_processed,
    shadow_cost_usd,
    -- 1000 satır başına maliyet (tahmini: 1 satır ~1KB)
    ROUND(shadow_cost_usd / NULLIF(bytes_processed / 1000.0, 0) * 1000, 8) AS query_cost_per_1000_rows,
    execution_time_seconds,
    run_date,
    start_time,
    end_time,
    CURRENT_TIMESTAMP() AS processed_at
FROM aggregated
