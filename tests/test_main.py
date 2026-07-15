"""Main FastAPI uygulaması testleri."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.ingestion.main import app

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
        patch("src.ingestion.main.usgs_fetcher.fetch", AsyncMock(return_value=([], {}))),
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
        patch("src.ingestion.main.kandilli_fetcher.fetch", AsyncMock(return_value=([], {}))),
        patch("src.ingestion.main.write_raw_json") as mock_gcs,
        patch("src.ingestion.main.load_to_staging") as mock_load,
    ):
        response = client.post("/ingest/kandilli")
        assert response.status_code == 200
        data = response.json()
        assert data["events_processed"] == 0
        mock_gcs.assert_not_called()
        mock_load.assert_not_called()
