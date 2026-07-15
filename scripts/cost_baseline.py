#!/usr/bin/env python3
"""Maliyet baseline ölçüm aracı — her modelin bytes_processed + shadow_cost değerini gösterir."""

from google.cloud import bigquery

PROJECT = "deprem-502519"
client = bigquery.Client(project=PROJECT)

models = [
    "deprem-502519.staging.stg_usgs_earthquakes",
    "deprem-502519.staging.int_earthquake_matches",
    "deprem-502519.staging.fct_unified_earthquakes",
    "deprem-502519.staging_marts.dm_earthquake_daily",
    "deprem-502519.staging_marts.fct_model_cost",
    "deprem-502519.staging_marts.dm_daily_pipeline_cost",
]

total_bytes = 0
print(f"\n{'='*60}")
print(f"📊 Maliyet Baseline Ölçümü — {PROJECT}")
print(f"{'='*60}\n")

for model in models:
    try:
        sql = f"SELECT * FROM `{model}` LIMIT 1000"
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        query_job = client.query(sql, job_config=job_config)
        b = query_job.total_bytes_processed or 0
        cost = b * 5.0 / 1099511627776
        total_bytes += b
        status = "✅"
    except Exception as e:
        b = 0
        cost = 0
        status = f"⚠️  ({str(e)[:60]})"
    
    print(f"  {status} {model:55s} {b:>12,} bytes  (${cost:.10f})")

total_cost = total_bytes * 5.0 / 1099511627776
print(f"\n  {'─'*80}")
print(f"  {'TOPLAM':55s} {total_bytes:>12,} bytes  (${total_cost:.10f})")
print(f"  {'TOPLAM (TiB)':55s} {total_bytes/1099511627776:.10f} TiB")
print(f"  {'MALİYET ($5/TiB)':55s} ${total_cost:.10f}")
print(f"\n{'=':>60}\n")
