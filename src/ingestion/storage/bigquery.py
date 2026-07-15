import logging
from typing import List

from google.cloud import bigquery

logger = logging.getLogger(__name__)

# Explicit schema — autodetect kapalı, kolon sırası ve tipleri sabit tutulur.
USGS_SCHEMA: List[bigquery.SchemaField] = [
    bigquery.SchemaField("ingestion_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ingestion_time", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("event_time", "TIMESTAMP"),
    bigquery.SchemaField("updated", "TIMESTAMP"),
    bigquery.SchemaField("mag", "FLOAT64"),
    bigquery.SchemaField("mag_type", "STRING"),
    bigquery.SchemaField("place", "STRING"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("tsunami", "INT64"),
    bigquery.SchemaField("sig", "INT64"),
    bigquery.SchemaField("net", "STRING"),
    bigquery.SchemaField("nst", "INT64"),
    bigquery.SchemaField("dmin", "FLOAT64"),
    bigquery.SchemaField("rms", "FLOAT64"),
    bigquery.SchemaField("gap", "FLOAT64"),
    bigquery.SchemaField("type", "STRING"),
    bigquery.SchemaField("alert", "STRING"),
    bigquery.SchemaField("cdi", "FLOAT64"),
    bigquery.SchemaField("mmi", "FLOAT64"),
    bigquery.SchemaField("felt", "INT64"),
    bigquery.SchemaField("lon", "FLOAT64"),
    bigquery.SchemaField("lat", "FLOAT64"),
    bigquery.SchemaField("depth_km", "FLOAT64"),
    bigquery.SchemaField("source_url", "STRING"),
    bigquery.SchemaField("raw_json", "JSON"),
]

KANDILLI_SCHEMA: List[bigquery.SchemaField] = [
    bigquery.SchemaField("ingestion_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ingestion_time", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("earthquake_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("date_time", "TIMESTAMP"),
    bigquery.SchemaField("created_at", "TIMESTAMP"),
    bigquery.SchemaField("mag", "FLOAT64"),
    bigquery.SchemaField("depth_km", "FLOAT64"),
    bigquery.SchemaField("lon", "FLOAT64"),
    bigquery.SchemaField("lat", "FLOAT64"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("location_tz", "STRING"),
    bigquery.SchemaField("provider", "STRING"),
    bigquery.SchemaField("epi_center_name", "STRING"),
    bigquery.SchemaField("epi_center_population", "INT64"),
    bigquery.SchemaField("closest_city_name", "STRING"),
    bigquery.SchemaField("closest_city_distance_km", "FLOAT64"),
    bigquery.SchemaField("location_properties", "JSON"),
    bigquery.SchemaField("raw_json", "JSON"),
]


def load_to_staging(
    client: bigquery.Client,
    dataset: str,
    source: str,
    gcs_uri: str,
    schema: List[bigquery.SchemaField],
) -> int:
    """GCS'teki JSONL'yi `_stg_{source}` staging tablosuna WRITE_TRUNCATE ile yükler.

    Autodetect kapalıdır — schema explicit verilir, kolon sırası garanti altında.
    """
    table_id = f"{client.project}.{dataset}._stg_{source}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=False,
    )

    load_job = client.load_table_from_uri(
        gcs_uri, destination=table_id, job_config=job_config
    )
    load_job.result()  # Senkron bekle — hata varsa exception fırlar.

    if load_job.errors:
        raise RuntimeError(f"Load job errors: {load_job.errors}")

    table = client.get_table(table_id)
    row_count = table.num_rows or 0
    logger.info(f"Loaded {row_count} rows into {table_id}")
    return row_count


def merge_to_raw(
    client: bigquery.Client,
    dataset: str,
    source: str,
) -> int:
    """Staging tablosunu raw tabloya MERGE ile upsert eder.

    USGS: event_id + updated karşılaştırması.
    Kandilli: earthquake_id + created_at karşılaştırması.
    """
    project = client.project

    if source == "usgs":
        target = f"`{project}.{dataset}.usgs_earthquakes`"
        staging = f"`{project}.{dataset}._stg_usgs`"
        sql = f"""
        MERGE {target} T
        USING {staging} S
        ON T.event_id = S.event_id
        WHEN MATCHED AND S.updated > T.updated THEN
          UPDATE SET
            ingestion_id = S.ingestion_id,
            ingestion_time = S.ingestion_time,
            event_time = S.event_time,
            updated = S.updated,
            mag = S.mag,
            mag_type = S.mag_type,
            place = S.place,
            status = S.status,
            tsunami = S.tsunami,
            sig = S.sig,
            net = S.net,
            nst = S.nst,
            dmin = S.dmin,
            rms = S.rms,
            gap = S.gap,
            type = S.type,
            alert = S.alert,
            cdi = S.cdi,
            mmi = S.mmi,
            felt = S.felt,
            lon = S.lon,
            lat = S.lat,
            depth_km = S.depth_km,
            source_url = S.source_url
        WHEN NOT MATCHED THEN
          INSERT ROW
        """
    elif source == "kandilli":
        target = f"`{project}.{dataset}.kandilli_earthquakes`"
        staging = f"`{project}.{dataset}._stg_kandilli`"
        sql = f"""
        MERGE {target} T
        USING {staging} S
        ON T.earthquake_id = S.earthquake_id
        WHEN MATCHED AND S.created_at > T.created_at THEN
          UPDATE SET
            ingestion_id = S.ingestion_id,
            ingestion_time = S.ingestion_time,
            date_time = S.date_time,
            created_at = S.created_at,
            mag = S.mag,
            depth_km = S.depth_km,
            lon = S.lon,
            lat = S.lat,
            title = S.title,
            location_tz = S.location_tz,
            provider = S.provider,
            epi_center_name = S.epi_center_name,
            epi_center_population = S.epi_center_population,
            closest_city_name = S.closest_city_name,
            closest_city_distance_km = S.closest_city_distance_km,
            location_properties = S.location_properties
        WHEN NOT MATCHED THEN
          INSERT ROW
        """
    else:
        raise ValueError(f"Unknown source: {source}")

    query_job = client.query(sql)
    result = query_job.result()  # MERGE tamamlanana kadar bekler.
    try:
        affected = (
            query_job.dml_stats.updated_row_count
            + query_job.dml_stats.inserted_row_count
            + query_job.dml_stats.deleted_row_count
        )
    except (AttributeError, TypeError):
        # Farklı BQ client sürümlerinde dml_stats attr isimleri değişebilir
        affected = 0
        if query_job.num_dml_affected_rows is not None:
            affected = query_job.num_dml_affected_rows
    logger.info(f"MERGE for {source} affected {affected} rows")
    return affected


def truncate_staging(
    client: bigquery.Client,
    dataset: str,
    source: str,
) -> None:
    """Staging tablosunu truncate eder — bir sonraki ingestion temiz başlasın."""
    table_id = f"{client.project}.{dataset}._stg_{source}"
    sql = f"TRUNCATE TABLE `{table_id}`"
    query_job = client.query(sql)
    query_job.result()
    logger.info(f"Truncated {table_id}")