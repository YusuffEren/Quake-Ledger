"""Main FastAPI uygulaması testleri."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.ingestion.main import app, event_to_bq_row
from src.ingestion.models import EarthquakeEvent

# get_bq_client her çağrıldığında MagicMock dönsün
import src.ingestion.main as main_mod

main_mod.get_bq_client = MagicMock(return_value=MagicMock())

client = TestClient(app)


def test_health():
    """/health endpoint'i 200 ve status=ok dönmeli."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ingest_usgs_no_events():
    """Hiç event yokken pipeline erken dönmeli (GCS/BQ çağrılmamalı)."""
    with (
        patch(
            "src.ingestion.main.usgs_fetcher.fetch", AsyncMock(return_value=([], {}))
        ),
        patch("src.ingestion.main.write_raw_json") as mock_gcs,
        patch("src.ingestion.main.load_to_staging") as mock_load,
    ):
        response = client.post("/ingest/usgs")
        assert response.status_code == 200
        data = response.json()
        assert data["events_processed"] == 0
        # GCS ve BQ çağrılmamalı
        mock_gcs.assert_not_called()
        mock_load.assert_not_called()


def test_ingest_kandilli_no_events():
    """Kandilli 304 dönünce pipeline erken dönmeli."""
    with (
        patch(
            "src.ingestion.main.kandilli_fetcher.fetch",
            AsyncMock(return_value=([], {})),
        ),
        patch("src.ingestion.main.write_raw_json") as mock_gcs,
        patch("src.ingestion.main.load_to_staging") as mock_load,
    ):
        response = client.post("/ingest/kandilli")
        assert response.status_code == 200
        data = response.json()
        assert data["events_processed"] == 0
        mock_gcs.assert_not_called()
        mock_load.assert_not_called()


def test_ingest_emsc_no_events():
    """EMSC için no-events testi — pipeline erken dönmeli (GCS/BQ çağrılmamalı)."""
    with (
        patch(
            "src.ingestion.main.emsc_fetcher.fetch", AsyncMock(return_value=([], {}))
        ),
        patch("src.ingestion.main.write_raw_json") as mock_gcs,
        patch("src.ingestion.main.load_to_staging") as mock_load,
    ):
        response = client.post("/ingest/emsc")
        assert response.status_code == 200
        data = response.json()
        assert data["events_processed"] == 0
        mock_gcs.assert_not_called()
        mock_load.assert_not_called()


def _make_usgs_event() -> EarthquakeEvent:
    """Happy-path testleri için minimal USGS event'i."""
    return EarthquakeEvent(
        source="usgs",
        event_id="us7000abcd",
        event_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        mag=5.0,
        place="Test place",
        lon=35.0,
        lat=38.0,
        depth_km=10.0,
        event_type="earthquake",
        raw_json={"id": "us7000abcd"},
    )


def test_ingest_usgs_happy_path():
    """USGS happy path — tüm storage zinciri mock'lanmış, 200 + doğru response."""
    event = _make_usgs_event()
    raw_response = {"type": "FeatureCollection", "features": [event.raw_json]}

    with (
        patch(
            "src.ingestion.main.usgs_fetcher.fetch",
            AsyncMock(return_value=([event], raw_response)),
        ),
        patch(
            "src.ingestion.main.write_raw_json", return_value="raw/usgs/x.json"
        ) as mock_gcs,
        patch(
            "src.ingestion.main.write_staging_jsonl",
            return_value="gs://bucket/x.jsonl",
        ) as mock_staging,
        patch("src.ingestion.main.cleanup_orphan_staging") as mock_cleanup,
        patch("src.ingestion.main.load_to_staging", return_value=1) as mock_load,
        patch("src.ingestion.main.merge_to_raw", return_value=1) as mock_merge,
        patch("src.ingestion.main.drop_staging") as mock_drop,
    ):
        response = client.post("/ingest/usgs")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["source"] == "usgs"
    assert data["events_processed"] == 1
    assert data["rows_merged"] == 1
    assert "ingestion_id" in data

    # Tüm zincir adımları çağrılmış olmalı
    mock_gcs.assert_called_once()
    mock_staging.assert_called_once()
    mock_cleanup.assert_called_once()
    mock_load.assert_called_once()
    mock_merge.assert_called_once()
    mock_drop.assert_called_once()


def test_ingest_usgs_drop_staging_fails_returns_200():
    """drop_staging hata fırlatsa bile MERGE başarılıysa 200 dönmeli.

    Veri raw tabloya yazılmış olduğu için staging DROP hatası false-negative
    500'e dönüştürülmemeli — Sorun 2'nin düzeltmesini doğrular.
    """
    event = _make_usgs_event()
    raw_response = {"type": "FeatureCollection", "features": []}

    with (
        patch(
            "src.ingestion.main.usgs_fetcher.fetch",
            AsyncMock(return_value=([event], raw_response)),
        ),
        patch("src.ingestion.main.write_raw_json", return_value="raw/usgs/x.json"),
        patch(
            "src.ingestion.main.write_staging_jsonl", return_value="gs://bucket/x.jsonl"
        ),
        patch("src.ingestion.main.cleanup_orphan_staging"),
        patch("src.ingestion.main.load_to_staging", return_value=1),
        patch("src.ingestion.main.merge_to_raw", return_value=1) as mock_merge,
        patch(
            "src.ingestion.main.drop_staging", side_effect=Exception("DROP failed")
        ) as mock_drop,
    ):
        response = client.post("/ingest/usgs")

    assert response.status_code == 200
    data = response.json()
    assert data["rows_merged"] == 1
    # MERGE mutlaka çalışmış olmalı (veri raw'da)
    mock_merge.assert_called_once()
    # DROP denendi ama hata bastırıldı
    mock_drop.assert_called_once()


def test_ingest_usgs_cleanup_orphan_fails_returns_200():
    """cleanup_orphan_staging hatası best-effort — ingestion'a engel olmamalı.

    Sorun 1'in düzeltmesini doğrular.
    """
    event = _make_usgs_event()
    raw_response = {"type": "FeatureCollection", "features": []}

    with (
        patch(
            "src.ingestion.main.usgs_fetcher.fetch",
            AsyncMock(return_value=([event], raw_response)),
        ),
        patch("src.ingestion.main.write_raw_json", return_value="raw/usgs/x.json"),
        patch(
            "src.ingestion.main.write_staging_jsonl", return_value="gs://bucket/x.jsonl"
        ),
        patch(
            "src.ingestion.main.cleanup_orphan_staging",
            side_effect=Exception("cleanup failed"),
        ),
        patch("src.ingestion.main.load_to_staging", return_value=1) as mock_load,
        patch("src.ingestion.main.merge_to_raw", return_value=1),
        patch("src.ingestion.main.drop_staging"),
    ):
        response = client.post("/ingest/usgs")

    assert response.status_code == 200
    # Cleanup fail olsa bile load/merge devam etmiş olmalı
    mock_load.assert_called_once()


# ---------------------------------------------------------------------------
# event_to_bq_row
# ---------------------------------------------------------------------------


def test_event_to_bq_row_usgs():
    """USGS satırı tüm USGS'ye özgü kolonları taşır."""
    ev = _make_usgs_event()
    row = event_to_bq_row(
        ev, "usgs", "ing-123", datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    )
    assert row["ingestion_id"] == "ing-123"
    assert row["event_id"] == "us7000abcd"
    assert row["mag"] == 5.0
    assert row["type"] == "earthquake"
    assert row["lon"] == 35.0
    assert row["lat"] == 38.0
    assert row["depth_km"] == 10.0
    assert row["event_time"] is not None
    assert row["raw_json"] is not None  # JSON string
    # USGS'ye özgü alanlar mevcut, Kandilli'ye özgü alanlar yok
    assert "updated" in row
    assert "earthquake_id" not in row
    assert "location_tz" not in row


def test_event_to_bq_row_emsc():
    """EMSC, USGS FDSN formatını paylaşır ama daha az kolon taşır."""
    ev = EarthquakeEvent(
        source="emsc",
        event_id="emsc-123",
        event_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        mag=4.5,
        mag_type="ml",
        place="EMSC place",
        lon=28.0,
        lat=41.0,
        depth_km=5.0,
        raw_json={"id": "emsc-123"},
    )
    row = event_to_bq_row(
        ev, "emsc", "ing-456", datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    )
    assert row["ingestion_id"] == "ing-456"
    assert row["event_id"] == "emsc-123"
    assert row["mag"] == 4.5
    assert row["mag_type"] == "ml"
    assert row["lon"] == 28.0
    assert row["lat"] == 41.0
    # EMSC şemasında olmayan USGS alanları burada yok
    assert "tsunami" not in row
    assert "sig" not in row
    # Kandilli alanları da yok
    assert "earthquake_id" not in row


def test_event_to_bq_row_kandilli():
    """Kandilli satırı earthquake_id + created_at + location kolonları taşır."""
    ev = EarthquakeEvent(
        source="kandilli",
        event_id="kd-001",
        event_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc),
        mag=3.2,
        depth_km=8.0,
        lon=29.0,
        lat=40.0,
        place="Istanbul",
        location_tz="Europe/Istanbul",
        provider="KOERI",
        raw_json={"id": "kd-001"},
    )
    row = event_to_bq_row(
        ev, "kandilli", "ing-789", datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    )
    assert row["ingestion_id"] == "ing-789"
    assert row["earthquake_id"] == "kd-001"
    assert row["mag"] == 3.2
    assert row["location_tz"] == "Europe/Istanbul"
    assert row["provider"] == "KOERI"
    assert row["title"] == "Istanbul"  # place → title mapping
    # Kandilli'de event_id (USGS) yok, earthquake_id var
    assert "event_id" not in row
    assert "updated" not in row


def test_event_to_bq_row_unknown_source_raises():
    """Bilinmeyen source ValueError — sessizce yanlış şema düşmemeli."""
    ev = _make_usgs_event()
    with pytest.raises(ValueError, match="Unknown source: bogus"):
        event_to_bq_row(
            ev, "bogus", "ing-000", datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
