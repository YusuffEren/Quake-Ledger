"""EMSC Fetcher — Avrupa Sismoloji Merkezi (seismicportal.eu) API'si.

EMSC, USGS'den farklı bir ölçüm ağı kullanır. Aynı depremi farklı
büyüklükte raporlayabilir → reconciliation hikâyesi için ideal ikinci kaynak.
"""

import logging
from datetime import datetime, timezone
from typing import List, Tuple

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import EMSC_URL
from fetchers.base import BaseFetcher
from models import EarthquakeEvent

logger = logging.getLogger(__name__)

_RETRY_DECORATOR = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
)


def _parse_emsc_time(value) -> datetime | None:
    """EMSC ISO8601 zamanını parse et. None/null/geçersizde None dön."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    if isinstance(value, str):
        try:
            # "2026-07-15T21:36:56.0Z" gibi
            normalized = value.replace("Z", "+00:00").replace(".0Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            logger.warning(f"EMSC time parse failed: {value!r}")
            return None
    return None


class EMSCFetcher(BaseFetcher):
    """EMSC seismicportal.eu FDSN feed'ini çeker ve normalize eder."""

    @property
    def source_name(self) -> str:
        return "emsc"

    @_RETRY_DECORATOR
    async def _get(self) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                EMSC_URL,
                headers={"User-Agent": "QuakeLedger/1.0 (contact@project)"},
            )
            if response.status_code != 200:
                raise httpx.HTTPError(f"EMSC returned status {response.status_code}")
            return response

    async def fetch(self) -> Tuple[List[EarthquakeEvent], dict]:
        try:
            response = await self._get()
        except httpx.TimeoutException as e:
            logger.error(f"EMSC request timed out: {e}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"EMSC HTTP error: {e}")
            raise

        try:
            payload = response.json()
        except ValueError as e:
            logger.error(f"EMSC JSON parse error: {e}")
            raise ValueError(f"EMSC response is not valid JSON: {e}") from e

        events: List[EarthquakeEvent] = []
        for feature in payload.get("features", []):
            props = feature.get("properties", {}) or {}

            # EMSC'de koordinatlar geometry.coordinates yerine props'ta
            lon = props.get("lon")
            lat = props.get("lat")
            depth_km = props.get("depth")

            # Zaman: ISO string
            event_time = _parse_emsc_time(props.get("time"))
            last_update = _parse_emsc_time(props.get("lastupdate"))

            # EMSC event ID
            event_id = str(props.get("source_id") or props.get("unid") or "")

            if not event_time:
                logger.warning(f"EMSC event {event_id}: no valid time, skipping")
                continue

            event = EarthquakeEvent(
                source="emsc",
                event_id=event_id,
                event_time=event_time,
                mag=props.get("mag"),
                depth_km=depth_km,
                lon=lon,
                lat=lat,
                place=props.get("flynn_region"),
                raw_json=feature,
                updated=last_update,
                mag_type=props.get("magtype"),
                event_type=props.get("evtype"),
            )
            events.append(event)

        logger.info(f"EMSC fetched {len(events)} events")
        return events, payload
