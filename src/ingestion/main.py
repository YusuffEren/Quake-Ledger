import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from google.cloud import bigquery

from config import BQ_DATASET, RAW_BUCKET
from fetchers.emsc import EMSCFetcher
from fetchers.kandilli import KandilliFetcher
from fetchers.usgs import USGSFetcher
from models import EarthquakeEvent
from storage.bigquery import (
    EMSC_SCHEMA,
    KANDILLI_SCHEMA,
    USGS_SCHEMA,
    cleanup_orphan_staging,
    drop_staging,
    load_to_staging,
    merge_to_raw,
)
from storage.gcs import write_raw_json, write_staging_jsonl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Quake-Ledger Ingestion")

# Fetcher'lar stateful (Kandilli ETag tutar) — process ömrünce tek instance.
usgs_fetcher = USGSFetcher()
emsc_fetcher = EMSCFetcher()
kandilli_fetcher = KandilliFetcher()

# BQ client'ı — lazy init: modül import edildiğinde değil, ilk kullanımda oluşur.
# Böylece GCP credentials olmayan ortamlarda (test, lint) import hatası vermez.
_bq_client: Optional[bigquery.Client] = None


def get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client()
    return _bq_client


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/ingest/usgs")
async def ingest_usgs():
    return await do_ingest("usgs", usgs_fetcher)


@app.post("/ingest/emsc")
async def ingest_emsc():
    return await do_ingest("emsc", emsc_fetcher)


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
    elif source == "emsc":
        # EMSC, USGS ile aynı FDSN GeoJSON formatını kullanır
        return {
            "ingestion_id": ingestion_id,
            "ingestion_time": _serialize_dt(ingestion_time),
            "event_id": ev.event_id,
            "event_time": _serialize_dt(ev.event_time),
            "updated": _serialize_dt(ev.updated),
            "mag": ev.mag,
            "mag_type": ev.mag_type,
            "place": ev.place,
            "lon": ev.lon,
            "lat": ev.lat,
            "depth_km": ev.depth_km,
            "source_url": ev.source_url,
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
        event_to_bq_row(ev, source, ingestion_id, ingestion_time) for ev in events
    ]

    # 4. JSONL staging → GCS
    try:
        staging_uri = write_staging_jsonl(RAW_BUCKET, source, bq_rows, ingestion_id)
    except Exception as e:
        logger.error(f"Staging JSONL write failed for {source}: {e}")
        raise HTTPException(status_code=500, detail=f"Staging error: {e}")

    # 5. Schema seçimi — bilinmeyen source programlama hatasıdır, erkenden fail et.
    if source == "usgs":
        schema = USGS_SCHEMA
    elif source == "emsc":
        schema = EMSC_SCHEMA
    elif source == "kandilli":
        schema = KANDILLI_SCHEMA
    else:
        raise ValueError(f"Unknown source: {source}")

    bq = get_bq_client()

    # Önceki crash'lerden kalma orphan staging tablolarını temizle.
    # Best-effort: cleanup başarısız olursa ingestion devam etmeli —
    # orphan temizliğinin yeni veri yazmayı engellemesi kabul edilemez.
    try:
        cleanup_orphan_staging(bq, BQ_DATASET, source)
    except Exception as e:
        logger.warning(
            f"cleanup_orphan_staging failed for {source} (best-effort, continuing): {e}"
        )

    # 6. Load staging + MERGE — kritik adımlar. Başarısız olursa veri raw
    # tabloya yazılmamış demektir; 500 dönmek doğru davranıştır.
    try:
        loaded = load_to_staging(
            bq, BQ_DATASET, source, staging_uri, schema, ingestion_id
        )
        logger.info(f"Staging loaded: {loaded} rows")

        affected = merge_to_raw(bq, BQ_DATASET, source, ingestion_id)
        logger.info(f"MERGE affected: {affected} rows")
    except Exception as e:
        logger.error(f"BigQuery pipeline failed for {source}: {e}")
        raise HTTPException(status_code=500, detail=f"BigQuery error: {e}")

    # 7. Drop staging — best-effort. MERGE başarılı olduğunda veri raw'dadır;
    # staging tablosu kalıntısı bir sonraki ingestion'ın cleanup'ı veya yaş
    # filtresi ile temizlenir. Bu yüzden DROP hatası 500'e çevrilmez.
    try:
        drop_staging(bq, BQ_DATASET, source, ingestion_id)
    except Exception as e:
        logger.error(
            f"drop_staging failed for {source} (best-effort, returning 200): {e}"
        )

    return {
        "status": "ok",
        "source": source,
        "ingestion_id": ingestion_id,
        "events_processed": len(events),
        "rows_merged": affected,
    }
