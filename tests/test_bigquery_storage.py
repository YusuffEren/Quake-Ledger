"""storage/bigquery.py birim testleri — mock BQ client ile.

Gerçek GCP çağrısı yapılmaz; tüm BQ etkileşimleri MagicMock üzerinden
doğrulanır. conftest.py'deki MockBigQuery pattern'i takip edilir.
"""

from unittest.mock import MagicMock

import pytest

from src.ingestion.storage.bigquery import (
    USGS_SCHEMA,
    _safe_ingestion_id,
    cleanup_orphan_staging,
    drop_staging,
    load_to_staging,
    merge_to_raw,
)

# Testler sabit tanımlayıcılarla tekrarlanabilir tutuldu.
_TEST_INGESTION_ID = "550e8400-e29b-41d4-a716-446655440000"
_TEST_SAFE_ID = "550e8400"  # tireler çıkarılıp lower, ilk 8 karakter
_TEST_PROJECT = "test-project"


# ---------------------------------------------------------------------------
# _safe_ingestion_id
# ---------------------------------------------------------------------------


def test_safe_ingestion_id_normal_uuid():
    """Tireler çıkarılır, lower yapılır, ilk 8 karakter alınır."""
    assert _safe_ingestion_id(_TEST_INGESTION_ID) == _TEST_SAFE_ID


def test_safe_ingestion_id_uppercase_hex_lowered():
    """Hex harfler lowercase olmalı — tablo adı büyük/küçük harfe duyarlı."""
    assert _safe_ingestion_id("ABCDEF12-1234-5678-9012-1234567890AB") == "abcdef12"


def test_safe_ingestion_id_empty_string():
    """Boş string → boş sonek. Edge case: çağıran "" geçerse tablo adı
    `_stg_usgs_` olur — istenmeyen ama patlamaz."""
    assert _safe_ingestion_id("") == ""


def test_safe_ingestion_id_none_raises():
    """None → AttributeError. Sessizce "" dönmek yerine açıkça patlamalı;
    yoksa None UUID sessizce boş tablo adı üretir ve hata debug edilemez."""
    with pytest.raises(AttributeError):
        _safe_ingestion_id(None)


# ---------------------------------------------------------------------------
# load_to_staging
# ---------------------------------------------------------------------------


def test_load_to_staging_returns_row_count_and_calls_client():
    """Doğru destination/GCS URI/schema ile yükler, num_rows döner."""
    client = MagicMock()
    client.project = _TEST_PROJECT

    load_job = MagicMock()
    load_job.errors = None
    client.load_table_from_uri.return_value = load_job

    table = MagicMock()
    table.num_rows = 42
    client.get_table.return_value = table

    gcs_uri = "gs://test-raw-bucket/raw/usgs/x.jsonl"
    rows = load_to_staging(
        client, "raw", "usgs", gcs_uri, USGS_SCHEMA, _TEST_INGESTION_ID
    )

    assert rows == 42
    # Senkron beklemiş olmalı
    load_job.result.assert_called_once()

    client.load_table_from_uri.assert_called_once()
    call = client.load_table_from_uri.call_args
    assert call.args[0] == gcs_uri
    assert (
        call.kwargs["destination"] == f"{_TEST_PROJECT}.raw._stg_usgs_{_TEST_SAFE_ID}"
    )
    # job_config explicit schema taşımış olmalı (autodetect kapalı)
    assert call.kwargs["job_config"].schema == USGS_SCHEMA

    client.get_table.assert_called_once_with(
        f"{_TEST_PROJECT}.raw._stg_usgs_{_TEST_SAFE_ID}"
    )


def test_load_to_staging_raises_on_job_errors():
    """load_job.errors set ise RuntimeError — yarım yük veri yazılmamış sayılır."""
    client = MagicMock()
    client.project = _TEST_PROJECT

    load_job = MagicMock()
    load_job.errors = [{"reason": "bad", "message": "boom"}]
    client.load_table_from_uri.return_value = load_job

    with pytest.raises(RuntimeError, match="Load job errors"):
        load_to_staging(
            client, "raw", "usgs", "gs://b/f.jsonl", USGS_SCHEMA, _TEST_INGESTION_ID
        )


def test_load_to_staging_zero_rows_returns_zero():
    """num_rows None/0 → 0 döner, exception değil (boş ama başarılı yük)."""
    client = MagicMock()
    client.project = _TEST_PROJECT
    load_job = MagicMock()
    load_job.errors = None
    client.load_table_from_uri.return_value = load_job

    table = MagicMock()
    table.num_rows = None
    client.get_table.return_value = table

    assert (
        load_to_staging(
            client, "raw", "usgs", "gs://b/f.jsonl", USGS_SCHEMA, _TEST_INGESTION_ID
        )
        == 0
    )


# ---------------------------------------------------------------------------
# merge_to_raw
# ---------------------------------------------------------------------------


def test_merge_to_raw_usgs_sql_template():
    """USGS: doğru target/staging/ON/WHEN clause'ları ve DML affected sayısı."""
    client = MagicMock()
    client.project = _TEST_PROJECT

    query_job = MagicMock()
    query_job.dml_stats.updated_row_count = 3
    query_job.dml_stats.inserted_row_count = 2
    query_job.dml_stats.deleted_row_count = 0
    client.query.return_value = query_job

    affected = merge_to_raw(client, "raw", "usgs", _TEST_INGESTION_ID)

    assert affected == 5
    query_job.result.assert_called_once()

    client.query.assert_called_once()
    sql = client.query.call_args.args[0]
    assert "MERGE" in sql
    assert "`test-project.raw.usgs_earthquakes`" in sql
    assert "`test-project.raw._stg_usgs_550e8400`" in sql
    assert "T.event_id = S.event_id" in sql
    assert "S.updated > T.updated" in sql


def test_merge_to_raw_emsc_sql_template():
    """EMSC: USGS'ten farklı target tablo adı, aynı event_id ON clause'u."""
    client = MagicMock()
    client.project = _TEST_PROJECT
    query_job = MagicMock()
    query_job.dml_stats.updated_row_count = 0
    query_job.dml_stats.inserted_row_count = 1
    query_job.dml_stats.deleted_row_count = 0
    client.query.return_value = query_job

    merge_to_raw(client, "raw", "emsc", _TEST_INGESTION_ID)

    sql = client.query.call_args.args[0]
    assert "`test-project.raw.emsc_earthquakes`" in sql
    assert "`test-project.raw._stg_emsc_550e8400`" in sql
    assert "T.event_id = S.event_id" in sql


def test_merge_to_raw_kandilli_sql_template():
    """Kandilli: earthquake_id + created_at ile MERGE (event_id + updated değil)."""
    client = MagicMock()
    client.project = _TEST_PROJECT
    query_job = MagicMock()
    query_job.dml_stats.updated_row_count = 0
    query_job.dml_stats.inserted_row_count = 4
    query_job.dml_stats.deleted_row_count = 0
    client.query.return_value = query_job

    affected = merge_to_raw(client, "raw", "kandilli", _TEST_INGESTION_ID)

    assert affected == 4
    sql = client.query.call_args.args[0]
    assert "`test-project.raw.kandilli_earthquakes`" in sql
    assert "`test-project.raw._stg_kandilli_550e8400`" in sql
    assert "T.earthquake_id = S.earthquake_id" in sql
    assert "S.created_at > T.created_at" in sql


def test_merge_to_raw_unknown_source_raises():
    """Bilinmeyen source ValueError — programlama hatası sessiz geçmemeli."""
    client = MagicMock()
    client.project = _TEST_PROJECT
    with pytest.raises(ValueError, match="Unknown source: bogus"):
        merge_to_raw(client, "raw", "bogus", _TEST_INGESTION_ID)


def test_merge_to_raw_dml_stats_fallback_to_num_dml_affected_rows():
    """dml_stats değerleri toplanamıyorsa num_dml_affected_rows fallback'e düşer.

    Bazı BQ client sürümlerinde dml_stats değerleri beklenmedik tipte dönebilir;
    bu durumda `+` işlemini desteklemez ve TypeError fırlar. object() ile
    toplanamaz — bu da except (AttributeError, TypeError) koluna girmeyi simüle eder.
    """
    client = MagicMock()
    client.project = _TEST_PROJECT
    query_job = MagicMock()
    # object() + object() → TypeError (toplama desteklenmiyor)
    query_job.dml_stats.updated_row_count = object()
    query_job.dml_stats.inserted_row_count = object()
    query_job.dml_stats.deleted_row_count = object()
    query_job.num_dml_affected_rows = 7
    client.query.return_value = query_job

    affected = merge_to_raw(client, "raw", "usgs", _TEST_INGESTION_ID)
    assert affected == 7


def test_merge_to_raw_dml_stats_fallback_zero_when_no_affected_rows():
    """Fallback yolu boşsa ve num_dml_affected_rows None ise 0 döner."""
    client = MagicMock()
    client.project = _TEST_PROJECT
    query_job = MagicMock()
    query_job.dml_stats.updated_row_count = object()
    query_job.dml_stats.inserted_row_count = object()
    query_job.dml_stats.deleted_row_count = object()
    query_job.num_dml_affected_rows = None
    client.query.return_value = query_job

    affected = merge_to_raw(client, "raw", "usgs", _TEST_INGESTION_ID)
    assert affected == 0


# ---------------------------------------------------------------------------
# drop_staging
# ---------------------------------------------------------------------------


def test_drop_staging_executes_drop_if_exists():
    """Doğru tabloya DROP TABLE IF EXISTS çalıştırır ve senkron bekler."""
    client = MagicMock()
    client.project = _TEST_PROJECT
    query_job = MagicMock()
    client.query.return_value = query_job

    drop_staging(client, "raw", "usgs", _TEST_INGESTION_ID)

    client.query.assert_called_once()
    sql = client.query.call_args.args[0]
    assert sql == "DROP TABLE IF EXISTS `test-project.raw._stg_usgs_550e8400`"
    query_job.result.assert_called_once()


# ---------------------------------------------------------------------------
# cleanup_orphan_staging
# ---------------------------------------------------------------------------


def test_cleanup_orphan_staging_no_tables():
    """Orphan yoksa yalnızca list sorgusu çalışır, DROP yok, 0 döner."""
    client = MagicMock()
    client.project = _TEST_PROJECT
    list_job = MagicMock()
    list_job.result.return_value = []
    client.query.return_value = list_job

    dropped = cleanup_orphan_staging(client, "raw", "usgs", max_age_hours=1)

    assert dropped == 0
    assert client.query.call_count == 1


def test_cleanup_orphan_staging_drops_each_table():
    """Bulunan her orphan tablo için ayrı DROP çalışır."""
    client = MagicMock()
    client.project = _TEST_PROJECT

    list_job = MagicMock()
    row1 = MagicMock()
    row1.table_name = "_stg_usgs_aabbccdd"
    row2 = MagicMock()
    row2.table_name = "_stg_usgs_eeff0011"
    list_job.result.return_value = [row1, row2]

    drop_job_1 = MagicMock()
    drop_job_2 = MagicMock()
    # 1 INFORMATION_SCHEMA list sorgusu + 2 DROP
    client.query.side_effect = [list_job, drop_job_1, drop_job_2]

    dropped = cleanup_orphan_staging(client, "raw", "usgs", max_age_hours=1)

    assert dropped == 2
    assert client.query.call_count == 3

    # İlk çağrı INFORMATION_SCHEMA list sorgusu
    list_sql = client.query.call_args_list[0].args[0]
    assert "INFORMATION_SCHEMA.TABLES" in list_sql
    assert "table_name LIKE @prefix" in list_sql
    assert "TIMESTAMP_DIFF" in list_sql
    # Query parameter'ları job_config ile taşınır
    assert client.query.call_args_list[0].kwargs["job_config"] is not None

    # Sonraki iki çağrı her tablo için DROP
    assert (
        client.query.call_args_list[1].args[0]
        == "DROP TABLE IF EXISTS `test-project.raw._stg_usgs_aabbccdd`"
    )
    assert (
        client.query.call_args_list[2].args[0]
        == "DROP TABLE IF EXISTS `test-project.raw._stg_usgs_eeff0011`"
    )


def test_cleanup_orphan_staging_continues_on_drop_error():
    """Tek DROP başarısız olsa bile kalan orphan'lar temizlenmeye devam eder.

    Sorun 3'ün düzeltmesini doğrular: döngü kırılmaz.
    """
    client = MagicMock()
    client.project = _TEST_PROJECT

    list_job = MagicMock()
    row1 = MagicMock()
    row1.table_name = "_stg_usgs_aabbccdd"
    row2 = MagicMock()
    row2.table_name = "_stg_usgs_eeff0011"
    list_job.result.return_value = [row1, row2]

    drop_fail_job = MagicMock()
    drop_fail_job.result.side_effect = Exception("permission denied")
    drop_ok_job = MagicMock()

    # İlk drop fail, ikinci ok
    client.query.side_effect = [list_job, drop_fail_job, drop_ok_job]

    dropped = cleanup_orphan_staging(client, "raw", "usgs", max_age_hours=1)

    # İlk drop fail olsa bile ikinci başarılı → sadece 1 sayılır
    assert dropped == 1
    # Yine de 3 query yapılmış olmalı (döngü kırılmadı)
    assert client.query.call_count == 3
