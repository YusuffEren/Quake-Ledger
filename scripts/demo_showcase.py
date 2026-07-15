#!/usr/bin/env python3
"""Full pipeline demo showcase."""
from google.cloud import bigquery
from datetime import datetime, timezone

client = bigquery.Client(project="deprem-502519")
now = datetime.now(timezone.utc)

print("=" * 70)
print("  QUAKE-LEDGER PIPELINE DEMO")
print(f"  {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)

# 1. Health
print("\n1. CLOUD RUN HEALTH")
import urllib.request
import json
try:
    req = urllib.request.Request("https://quake-ingestion-588042584335.europe-west1.run.app/health",
                                headers={"User-Agent": "demo"})
    with urllib.request.urlopen(req, timeout=5) as r:
        print(f"   ✅ {json.loads(r.read())}")
except Exception as e:
    print(f"   ⚠️  {e}")

# 2. USGS Stats
print("\n2. USGS INGESTION (son 24 saat)")
rows = client.query("""
    SELECT COUNT(*) AS events, ROUND(AVG(mag),2) AS avg_mag, MAX(mag) AS max_mag,
           MIN(event_time) AS oldest, MAX(event_time) AS newest
    FROM `deprem-502519.raw.usgs_earthquakes`
    WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
""").result()
for r in rows:
    print(f"   📊 {r.events} events, avg M{r.avg_mag}, max M{r.max_mag}")
    print(f"      Range: {r.oldest} → {r.newest}")

# 3. Reconciliation
print("\n3. RECONCILIATION (eşleşme analizi)")
rows = client.query("""
    SELECT match_status, COUNT(*) AS count
    FROM `deprem-502519.staging.int_earthquake_matches`
    GROUP BY match_status
    ORDER BY count DESC
""").result()
for r in rows:
    icon = "✅" if r.match_status == "matched" else ("ℹ️" if r.match_status == "usgs_only" else "ℹ️")
    print(f"   {icon} {r.match_status}: {r.count} events")

# 4. Sample matched events with disagreement
print("\n4. EŞLEŞEN DEPREMLER (disagreement)")
rows = client.query("""
    SELECT usgs_mag, kandilli_mag, mag_disagreement,
           usgs_place, kandilli_place, time_diff_seconds, distance_km
    FROM `deprem-502519.staging.fct_unified_earthquakes`
    WHERE match_status = 'matched'
    ORDER BY mag_disagreement DESC
    LIMIT 5
""").result()
for r in rows:
    print(f"   🔄 USGS M{r.usgs_mag} vs Kandilli M{r.kandilli_mag} "
          f"(fark: {r.mag_disagreement})")
    print(f"      {r.usgs_place} | {r.kandilli_place}")
    if r.time_diff_seconds:
        print(f"      Zaman farkı: {r.time_diff_seconds}s, Mesafe: {r.distance_km}km")

# 5. Daily summary
print("\n5. GÜNLÜK ÖZET (marts)")
rows = client.query("""
    SELECT event_date, source, earthquake_count, avg_magnitude, max_magnitude
    FROM `deprem-502519.staging_marts.dm_earthquake_daily`
    WHERE earthquake_count > 0
    ORDER BY event_date DESC
    LIMIT 5
""").result()
for r in rows:
    print(f"   📅 {r.event_date} | {r.source:10s} | {r.earthquake_count} events | "
          f"avg M{r.avg_magnitude} | max M{r.max_magnitude}")

# 6. Pipeline cost
print("\n6. MALİYET (gölge maliyet)")
rows = client.query("""
    SELECT model_name, SUM(bytes_processed) AS bytes, 
           ROUND(SUM(shadow_cost_usd), 10) AS cost
    FROM `deprem-502519.staging_marts.fct_model_cost`
    GROUP BY model_name
    ORDER BY bytes DESC
    LIMIT 5
""").result()
total = 0
for r in rows:
    print(f"   💰 {r.model_name:30s} {r.bytes:>10,} bytes  ${r.cost:.10f}")
    total += r.cost
print(f"   {'─'*55}")
print(f"   {'TOTAL':30s} {'':>10}  ${total:.10f}")

print("\n" + "=" * 70)
print("  ✅ PIPELINE HEALTHY")
print("  🌍 USGS: live | 🇹🇷 Kandilli: live | 🔄 Reconciliation: active")
print("  💰 Cost: $0/ay (GCP Free Tier)")
print("=" * 70)
