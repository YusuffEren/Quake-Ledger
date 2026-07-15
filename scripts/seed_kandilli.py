#!/usr/bin/env python3
"""
Kandilli örnek verisi oluşturma scripti.
USGS'deki Türkiye yakını depremler için Kandilli benzeri kayıtlar oluşturur.
Böylece reconciliation modeli eşleştirme yapabilir.
"""

import json
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery

PROJECT = "deprem-502519"
DATASET = "raw"
TABLE = "kandilli_earthquakes"

client = bigquery.Client(project=PROJECT)

# USGS'den Türkiye yakını depremleri al
query = f"""
SELECT event_id, mag, lat, lon, depth_km, place, event_time
FROM `{PROJECT}.{DATASET}.usgs_earthquakes`
WHERE (place LIKE '%Turkey%' OR place LIKE '%Mediterranean%')
   OR (lat BETWEEN 35 AND 43 AND lon BETWEEN 25 AND 46)
ORDER BY event_time DESC
"""

rows = client.query(query).result()
usgs_events = list(rows)
print(f"USGS'de Türkiye bölgesinde {len(usgs_events)} deprem bulundu")

if not usgs_events:
    # Türkiye yakını yoksa, en yakın depremleri al ve koordinat değiştir
    print("Türkiye bölgesinde USGS verisi yok, örnek veri oluşturuluyor...")
    sample_earthquakes = [
        {
            "event_id": "TR20260715001",
            "earthquake_id": "TR20260715001",
            "mag": 4.2,
            "depth_km": 10.5,
            "lon": 38.21,
            "lat": 38.12,
            "title": "MALATYA - Dogansehir",
            "date_time": "2026-07-15 18:45:00",
            "created_at": "2026-07-15 18:50:00",
            "location_tz": "Europe/Istanbul",
            "provider": "kandilli",
            "epi_center_name": "Dogansehir",
            "epi_center_population": 45000,
            "closest_city_name": "Malatya",
            "closest_city_distance_km": 12.4,
        },
        {
            "event_id": "TR20260715002",
            "earthquake_id": "TR20260715002",
            "mag": 2.8,
            "depth_km": 7.2,
            "lon": 39.05,
            "lat": 38.68,
            "title": "ELAZIG - Sivrice",
            "date_time": "2026-07-15 14:30:00",
            "created_at": "2026-07-15 14:35:00",
            "location_tz": "Europe/Istanbul",
            "provider": "kandilli",
            "epi_center_name": "Sivrice",
            "epi_center_population": 12000,
            "closest_city_name": "Elazig",
            "closest_city_distance_km": 5.1,
        },
        {
            "event_id": "TR20260715003",
            "earthquake_id": "TR20260715003",
            "mag": 3.1,
            "depth_km": 8.0,
            "lon": 27.15,
            "lat": 38.35,
            "title": "IZMIR - Gaziemir",
            "date_time": "2026-07-15 10:15:00",
            "created_at": "2026-07-15 10:20:00",
            "location_tz": "Europe/Istanbul",
            "provider": "kandilli",
            "epi_center_name": "Gaziemir",
            "epi_center_population": 130000,
            "closest_city_name": "Izmir",
            "closest_city_distance_km": 8.0,
        },
    ]
    
    rows_to_insert = []
    for eq in sample_earthquakes:
        row = {
            "ingestion_id": str(uuid.uuid4()),
            "ingestion_time": datetime.now(timezone.utc).isoformat(),
            "earthquake_id": eq["earthquake_id"],
            "date_time": eq["date_time"],
            "created_at": eq["created_at"],
            "mag": eq["mag"],
            "depth_km": eq["depth_km"],
            "lon": eq["lon"],
            "lat": eq["lat"],
            "title": eq["title"],
            "location_tz": eq["location_tz"],
            "provider": eq["provider"],
            "epi_center_name": eq["epi_center_name"],
            "epi_center_population": eq["epi_center_population"],
            "closest_city_name": eq["closest_city_name"],
            "closest_city_distance_km": eq["closest_city_distance_km"],
            "raw_json": json.dumps(eq),
        }
        rows_to_insert.append(row)
    
    table = client.get_table(f"{PROJECT}.{DATASET}.{TABLE}")
    errors = client.insert_rows_json(table, rows_to_insert)
    if errors:
        print(f"Hata: {errors}")
    else:
        print(f"✅ {len(rows_to_insert)} örnek Kandilli depremi eklendi!")
    
    print("\nEklenen depremler:")
    for eq in sample_earthquakes:
        print(f"  M{eq['mag']} - {eq['title']} - {eq['date_time']}")
else:
    print(f"USGS'de zaten Türkiye verisi var, Kandilli'ye ekleniyor...")
    # Transform USGS events to Kandilli format
    rows_to_insert = []
    for row in usgs_events:
        kandilli_row = {
            "ingestion_id": str(uuid.uuid4()),
            "ingestion_time": datetime.now(timezone.utc).isoformat(),
            "earthquake_id": f"TR_{row.event_id}",
            "date_time": row.event_time.isoformat(),
            "created_at": row.event_time.isoformat(),
            "mag": round(row.mag + 0.1, 1) if row.mag else 3.0,  # Slight difference for disagreement
            "depth_km": row.depth_km,
            "lon": row.lon,
            "lat": row.lat,
            "title": f"{row.place} [Kandilli]",
            "location_tz": "Europe/Istanbul",
            "provider": "kandilli",
        }
        rows_to_insert.append(kandilli_row)
    
    table = client.get_table(f"{PROJECT}.{DATASET}.{TABLE}")
    errors = client.insert_rows_json(table, rows_to_insert)
    if errors:
        print(f"Hata: {errors}")
    else:
        print(f"✅ {len(rows_to_insert)} Kandilli kaydı eklendi!")
