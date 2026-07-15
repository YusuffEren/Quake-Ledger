#!/usr/bin/env python3
"""Veri kontrol scripti."""
from google.cloud import bigquery

client = bigquery.Client(project="deprem-502519")

print("=== KANDILLI RAW ===")
rows = client.query("SELECT earthquake_id, mag, title, date_time, lon, lat FROM `deprem-502519.raw.kandilli_earthquakes` LIMIT 10").result()
for r in rows:
    print(f"  {r.earthquake_id} M{r.mag} {r.title} @ {r.date_time} [{r.lon}, {r.lat}]")

print("\n=== USGS RAW (Türkiye) ===")
rows = client.query("SELECT event_id, mag, place, event_time FROM `deprem-502519.raw.usgs_earthquakes` WHERE place LIKE '%Turkey%' OR place LIKE '%turkey%' LIMIT 10").result()
for r in rows:
    print(f"  {r.event_id} M{r.mag} {r.place} @ {r.event_time}")

print("\n=== USGS TOPLAM ===")
row = client.query("SELECT COUNT(*) AS c FROM `deprem-502519.raw.usgs_earthquakes`").result()
for r in row:
    print(f"  {r.c} kayıt")
