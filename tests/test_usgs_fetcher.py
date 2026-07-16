"""USGS fetcher birim testleri."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pytest import approx

from src.ingestion.fetchers.usgs import USGSFetcher

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def usgs_fixture():
    with open(FIXTURE_DIR / "usgs_sample.json") as f:
        return json.load(f)


@pytest.fixture
def usgs_fetcher():
    return USGSFetcher()


@pytest.mark.asyncio
async def test_fetch_happy_path(usgs_fetcher, usgs_fixture):
    """Happy path: USGS'den gelen GeoJSON doğru parse edilmeli."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = usgs_fixture

    with patch.object(usgs_fetcher, "_get", AsyncMock(return_value=mock_response)):
        events, raw = await usgs_fetcher.fetch()

    assert len(events) == 4
    assert raw == usgs_fixture

    # İlk event'i kontrol et
    ev = events[0]
    assert ev.source == "usgs"
    assert ev.event_id == "us7000abcd1"
    assert ev.mag == 4.2
    assert ev.lon == approx(38.21)
    assert ev.lat == approx(38.12)
    assert ev.depth_km == approx(10.5)
    assert ev.place == "12 km SSE of Malatya, Turkey"
    assert ev.raw_json is not None


@pytest.mark.asyncio
async def test_fetch_empty_features(usgs_fetcher):
    """Hiç feature yoksa boş liste dönmeli."""
    empty_payload = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {"count": 0},
    }
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = empty_payload

    with patch.object(usgs_fetcher, "_get", AsyncMock(return_value=mock_response)):
        events, raw = await usgs_fetcher.fetch()

    assert len(events) == 0


@pytest.mark.asyncio
async def test_fetch_http_error_propagates(usgs_fetcher):
    """_get HTTPError fırlatınca fetch de HTTPError fırlatmalı."""
    with patch.object(
        usgs_fetcher, "_get", AsyncMock(side_effect=httpx.HTTPError("500"))
    ):
        with pytest.raises(httpx.HTTPError):
            await usgs_fetcher.fetch()
