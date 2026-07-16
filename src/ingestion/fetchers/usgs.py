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

from config import USGS_URL
from fetchers.base import BaseFetcher
from models import EarthquakeEvent

logger = logging.getLogger(__name__)

# USGS summary endpoint'i nadiren 5xx döner; transient hatalar için retry şart.
_RETRY_DECORATOR = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
)


class USGSFetcher(BaseFetcher):
    """USGS all_hour GeoJSON feed'ini çeker ve normalize eder."""

    @property
    def source_name(self) -> str:
        return "usgs"

    @_RETRY_DECORATOR
    async def _get(self) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                USGS_URL,
                headers={"User-Agent": "QuakeLedger/1.0 (contact@project)"},
            )
            # 200 dışı durumlar retry'ı tetiklemeli — HTTPError raise ediyoruz.
            if response.status_code != 200:
                raise httpx.HTTPError(f"USGS returned status {response.status_code}")
            return response

    async def fetch(self) -> Tuple[List[EarthquakeEvent], dict]:
        try:
            response = await self._get()
        except httpx.TimeoutException as e:
            logger.error(f"USGS request timed out: {e}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"USGS HTTP error: {e}")
            raise

        try:
            payload = response.json()
        except ValueError as e:
            logger.error(f"USGS JSON parse error: {e}")
            raise ValueError(f"USGS response is not valid JSON: {e}") from e

        events: List[EarthquakeEvent] = []
        for feature in payload.get("features", []):
            props = feature.get("properties", {}) or {}
            geometry = feature.get("geometry", {}) or {}
            coords = geometry.get("coordinates", [0.0, 0.0, 0.0])

            # GeoJSON coords sırası: [lon, lat, depth_km]
            # Koordinat yoksa None — 0.0 Null Island (0,0) yanıltısı yaratır.
            lon = coords[0] if len(coords) > 0 else None
            lat = coords[1] if len(coords) > 1 else None
            depth_km = coords[2] if len(coords) > 2 else None

            # USGS epoch'ları milisaniye cinsinden verir.
            # utcfromtimestamp Python 3.12'de deprecated — fromtimestamp + tz kullan.
            event_time_ms = props.get("time")
            updated_ms = props.get("updated")
            event_time = (
                datetime.fromtimestamp(event_time_ms / 1000.0, tz=timezone.utc)
                if event_time_ms is not None
                else None
            )
            updated = (
                datetime.fromtimestamp(updated_ms / 1000.0, tz=timezone.utc)
                if updated_ms is not None
                else None
            )

            event = EarthquakeEvent(
                source="usgs",
                event_id=feature.get("id", ""),
                event_time=event_time,
                mag=props.get("mag"),
                depth_km=depth_km,
                lon=lon,
                lat=lat,
                place=props.get("place"),
                raw_json=feature,
                updated=updated,
                mag_type=props.get("magType"),
                status=props.get("status"),
                tsunami=props.get("tsunami"),
                sig=props.get("sig"),
                net=props.get("net"),
                nst=props.get("nst"),
                dmin=props.get("dmin"),
                rms=props.get("rms"),
                gap=props.get("gap"),
                event_type=props.get("type"),
                alert=props.get("alert"),
                cdi=props.get("cdi"),
                mmi=props.get("mmi"),
                felt=props.get("felt"),
                source_url=props.get("url"),
            )
            events.append(event)

        logger.info(f"USGS fetched {len(events)} events")
        return events, payload
