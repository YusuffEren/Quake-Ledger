import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from google.cloud import bigquery

from config import BQ_DATASET, RAW_BUCKET
from fetchers.kandilli import KandilliFetcher
from fetchers.usgs import USGSFetcher
from models import EarthquakeEvent
from storage.bigquery import (
    KANDILLI_SCHEMA,
    USGS_SCHEMA,
    load_to_staging,
    merge_to_raw,
    truncate_staging,
)
from storage.gcs import write_raw_json, write_staging_jsonl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Quake-Ledger Ingestion")

# Fetcher'lar stateful (Kandilli ETag tutar) — process ömrünce tek instance.
usgs_fetcher = USGSFetcher()
kandilli_fetcher = KandilliFetcher()

# BQ client'ı process ömrünce tek instance — her istekte yeniden yaratmak
# gereksiz bağlantı yükü yaratır. Modül import edildiğinde auth çözülür.
bq_client = bigquery.Client()


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/ingest/usgs")
async def ingest_usgs():
    return await do_ingest("usgs", usgs_fetcher)


@app.post("/ingest/kandilli")
async def ingest_kandilli():
    return await do_ingest("kandilli", kandilli_fetcher)


def _serialize_dt(value: datetime | None) -> str | None:
    """BQ TIMESTAMP alanları için ISO8601 string; None None olarak kalsın."""
    if value is None:
        return None
    # Aware datetime'leri UTC'ye normalize edip ISO formatında veriyoruz.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _serialize_json(value: Any) -> str | None:
    """BQ JSON alanları için string serialize — None None olarak kalsın."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def event_to_bq_row(
    ev: EarthquakeEvent,
    source: str,
    ingestion_id: str,
    ingestion_time: datetime,
) -> dict:
    """EarthquakeEvent → BQ satırı. Kaynak tipine göre farklı kolon seti."""
    if source == "usgs":
        return {
            "ingestion_id": ingestion_id,
            "ingestion_time": _serialize_dt(ingestion_time),
            "event_id": ev.event_id,
            "event_time": _serialize_dt(ev.event_time),
            "updated": _serialize_dt(ev.updated),
            "mag": ev.mag,
            "mag_type": ev.mag_type,
            "place": ev.place,
            "status": ev.status,
            "tsunami": ev.tsunami,
            "sig": ev.sig,
            "net": ev.net,
            "nst": ev.nst,
            "dmin": ev.dmin,
            "rms": ev.rms,
            "gap": ev.gap,
            "type": ev.event_type,
            "alert": ev.alert,
            "cdi": ev.cdi,
            "mmi": ev.mmi,
            "felt": ev.felt,
            "lon": ev.lon,
            "lat": ev.lat,
            "depth_km": ev.depth_km,
            "source_url": ev.source_url,
            "raw_json": _serialize_json(ev.raw_json),
        }
    elif source == "kandilli":
        return {
            "ingestion_id": ingestion_id,
            "ingestion_time": _serialize_dt(ingestion_time),
            "earthquake_id": ev.event_id,
            "date_time": _serialize_dt(ev.event_time),
            "created_at": _serialize_dt(ev.created_at),
            "mag": ev.mag,
            "depth_km": ev.depth_km,
            "lon": ev.lon,
            "lat": ev.lat,
            "title": ev.place,
            "location_tz": ev.location_tz,
            "provider": ev.provider,
            "epi_center_name": ev.epi_center_name,
            "epi_center_population": ev.epi_center_population,
            "closest_city_name": ev.closest_city_name,
            "closest_city_distance_km": ev.closest_city_distance_km,
            "location_properties": _serialize_json(ev.location_properties),
            "raw_json": _serialize_json(ev.raw_json),
        }
    else:
        raise ValueError(f"Unknown source: {source}")


async def do_ingest(source: str, fetcher):
    ingestion_id = str(uuid.uuid4())
    ingestion_time = datetime.now(timezone.utc)

    # 1. Fetch
    try:
        events, raw_response = await fetcher.fetch()
    except Exception as e:
        logger.error(f"Fetch failed for {source}: {e}")
        raise HTTPException(status_code=502, detail=f"Fetch error: {e}")

    if not events:
        logger.info(f"No events from {source}")
        return {"status": "ok", "source": source, "events_processed": 0}

    # 2. Raw JSON → GCS (304 durumunda zaten buraya gelmeyiz)
    try:
        gcs_path = write_raw_json(RAW_BUCKET, source, raw_response, ingestion_time)
        logger.info(f"Raw written: {gcs_path}")
    except Exception as e:
        logger.error(f"GCS write failed for {source}: {e}")
        raise HTTPException(status_code=500, detail=f"GCS error: {e}")

    # 3. Transform events → BQ rows
    bq_rows = [
        event_to_bq_row(ev, source, ingestion_id, ingestion_time)
        for ev in events
    ]

    # 4. JSONL staging → GCS
    try:
        staging_uri = write_staging_jsonl(RAW_BUCKET, source, bq_rows, ingestion_id)
    except Exception as e:
        logger.error(f"Staging JSONL write failed for {source}: {e}")
        raise HTTPException(status_code=500, detail=f"Staging error: {e}")

    # 5. Load staging → BQ
    try:
        schema = USGS_SCHEMA if source == "usgs" else KANDILLI_SCHEMA
        loaded = load_to_staging(bq_client, BQ_DATASET, source, staging_uri, schema)
        logger.info(f"Staging loaded: {loaded} rows")

        # 6. MERGE staging → raw
        affected = merge_to_raw(bq_client, BQ_DATASET, source)
        logger.info(f"MERGE affected: {affected} rows")

        # 7. Truncate staging
        truncate_staging(bq_client, BQ_DATASET, source)
    except Exception as e:
        logger.error(f"BigQuery pipeline failed for {source}: {e}")
        raise HTTPException(status_code=500, detail=f"BigQuery error: {e}")

    return {
        "status": "ok",
        "source": source,
        "ingestion_id": ingestion_id,
        "events_fetched": len(events),
        "rows_merged": affected,
    }