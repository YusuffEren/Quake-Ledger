import hashlib
import json
import logging
from datetime import datetime
from typing import List, Optional

from google.cloud import storage

logger = logging.getLogger(__name__)


def _content_hash(data: dict) -> str:
    """JSON içeriğinin MD5 hash'inin ilk 8 karakteri — dedup için dosya adında kullanılır."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:8]


def write_raw_json(
    bucket_name: str,
    source: str,
    data: dict,
    ingestion_time: datetime,
    content_hash: Optional[str] = None,
) -> str:
    """Ham API yanıtını GCS'e partition-style path ile yazar.

    Path: raw/{source}/year=Y/month=M/day=D/hour=H/{ts}_{hash}.json
    Aynı içerik aynı hash ürettiği için overwrite idempotent'tir.
    """
    if data is None:
        raise ValueError("data must not be None")

    bucket = storage.Client().bucket(bucket_name)
    ts = ingestion_time.strftime("%Y%m%dT%H%M%S")
    chash = content_hash or _content_hash(data)
    path = (
        f"raw/{source}/year={ingestion_time.year:04d}"
        f"/month={ingestion_time.month:02d}"
        f"/day={ingestion_time.day:02d}"
        f"/hour={ingestion_time.hour:02d}"
        f"/{ts}_{chash}.json"
    )
    blob = bucket.blob(path)
    blob.upload_from_string(
        json.dumps(data, ensure_ascii=False),
        content_type="application/json",
    )
    logger.info(f"Raw JSON written to gs://{bucket_name}/{path}")
    return path


def write_staging_jsonl(
    bucket_name: str,
    source: str,
    rows: List[dict],
    ingestion_id: str,
) -> str:
    """BQ satırlarını JSONL olarak staging path'ine yazar, gs:// URI döner."""
    if not rows:
        raise ValueError("rows must not be empty")

    bucket = storage.Client().bucket(bucket_name)
    path = f"raw/{source}/_staging/{ingestion_id}.jsonl"
    blob = bucket.blob(path)
    payload = "\n".join(
        json.dumps(row, ensure_ascii=False) for row in rows
    )
    blob.upload_from_string(payload, content_type="application/jsonl")
    gcs_uri = f"gs://{bucket_name}/{path}"
    logger.info(f"Staging JSONL written to {gcs_uri}")
    return gcs_uri