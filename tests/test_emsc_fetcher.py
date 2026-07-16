"""EMSC fetcher birim testleri."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pytest import approx

from src.ingestion.fetchers.emsc import EMSCFetcher

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def emsc_fixture():
    with open(FIXTURE_DIR / "emsc_sample.json") as f:
        return json.load(f)


@pytest.fixture
def emsc_fetcher():
    return EMSCFetcher()


@pytest.mark.asyncio
async def test_fetch_happy_path(emsc_fetcher, emsc_fixture):
    """Happy path: EMSC yanıtı doğru parse edilmeli."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = emsc_fixture

    with patch.object(emsc_fetcher, "_get", AsyncMock(return_value=mock_response)):
        events, raw = await emsc_fetcher.fetch()

    assert len(events) == 2
    assert raw == emsc_fixture

    ev = events[0]
    assert ev.source == "emsc"
    assert ev.event_id == "emsc_test_001"
    assert ev.mag == 3.5
    assert ev.lon == approx(38.21)
    assert ev.lat == approx(38.12)
    assert ev.depth_km == approx(10.5)
    assert ev.place == "MALATYA, TURKEY"


@pytest.mark.asyncio
async def test_fetch_no_events(emsc_fetcher):
    """Hiç event yoksa boş liste dönmeli."""
    empty_payload = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {"count": 0},
    }
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = empty_payload

    with patch.object(emsc_fetcher, "_get", AsyncMock(return_value=mock_response)):
        events, raw = await emsc_fetcher.fetch()

    assert len(events) == 0


@pytest.mark.asyncio
async def test_fetch_parse_time_formats(emsc_fetcher, emsc_fixture):
    """Epoch ms time format da çalışmalı."""
    emsc_fixture["features"][0]["properties"]["time"] = 1719503100000  # epoch ms
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = emsc_fixture

    with patch.object(emsc_fetcher, "_get", AsyncMock(return_value=mock_response)):
        events, _ = await emsc_fetcher.fetch()

    assert len(events) == 2
    assert events[0].event_time is not None
