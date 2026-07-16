import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import KANDILLI_URL
from fetchers.base import BaseFetcher
from models import EarthquakeEvent

logger = logging.getLogger(__name__)

_ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")

_RETRY_DECORATOR = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
)

# Halka açık Kandilli proxy'sini darboğazlamamak için istekler arası min 15 sn.
_MIN_REQUEST_INTERVAL_SECONDS = 15


def _parse_istanbul_to_utc(value) -> Optional[datetime]:
    """`Europe/Istanbul` ile gelen zaman damgasını aware UTC'ye çevirir.

    Kandilli API'si yerel saati string olarak verir; UTC'ye normalize etmeden
    BQ'ya yazmak saat yazışımlarına yol açar. Bazı yanıtlar epoch ms (int/float)
    dönebilir — bu durumda doğrudan UTC'ye çeviririz.
    """
    if value is None:
        return None
    # Epoch milisaniye (int/float) — string metodu çağrılmadan önce tip kontrolü
    # şart, yoksa AttributeError fırlar.
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    # String format: "2024-06-27 18:45:00" veya "2024.06.27 18:45:00"
    if isinstance(value, str):
        try:
            normalized = value.replace(".", "-")
            local_dt = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
            return local_dt.replace(tzinfo=_ISTANBUL_TZ).astimezone(timezone.utc)
        except ValueError:
            try:
                # ISO 8601 fallback: "2024-06-27T18:45:00Z" gibi
                normalized = value.replace("Z", "+00:00").replace(".", "-")
                local_dt = datetime.fromisoformat(normalized)
                if local_dt.tzinfo is None:
                    local_dt = local_dt.replace(tzinfo=_ISTANBUL_TZ)
                return local_dt.astimezone(timezone.utc)
            except ValueError as e:
                logger.warning(f"Kandilli timestamp parse failed: {value!r} ({e})")
                return None
    logger.warning(
        f"Kandilli timestamp unexpected type: {type(value).__name__} ({value!r})"
    )
    return None


class KandilliFetcher(BaseFetcher):
    """Kandilli live deprem API'sini çeker; ETag ile gereksiz yükü engeller."""

    # ETag sınıf bazında saklanır — aynı process içindeki ardışık çağrılar
    # arasında cache'lenmiş yanıt tespit edip 304 döndürebiliriz.
    _etag: Optional[str] = None
    _last_request_ts: float = 0.0

    @property
    def source_name(self) -> str:
        return "kandilli"

    async def _enforce_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = _MIN_REQUEST_INTERVAL_SECONDS - elapsed
        if wait > 0:
            logger.info(f"Kandilli rate-limit: sleeping {wait:.1f}s")
            await asyncio.sleep(wait)

    @_RETRY_DECORATOR
    async def _get(self) -> httpx.Response:
        headers = {"User-Agent": "QuakeLedger/1.0 (contact@project)"}
        if self._etag is not None:
            headers["If-None-Match"] = self._etag

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(KANDILLI_URL, headers=headers)
            # 304 geçerli bir "veri değişmedi" yanıtıdır — retry'a girmemeli.
            if response.status_code == 304:
                return response
            # 200 dışı her şey retry'ı tetikler.
            if response.status_code != 200:
                raise httpx.HTTPError(
                    f"Kandilli returned status {response.status_code}"
                )
            return response

    async def fetch(self) -> Tuple[List[EarthquakeEvent], dict]:
        await self._enforce_rate_limit()

        try:
            response = await self._get()
        except httpx.TimeoutException as e:
            logger.error(f"Kandilli request timed out: {e}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Kandilli HTTP error: {e}")
            raise

        # Başarılı yanıt alındı (200 veya 304) — rate-limit penceresi
        # ancak şimdi başlamalı. Request öncesi set edilseydi, başarısız bir
        # denemeden sonra bekleme süresi yanlış kısalmış olurdu.
        self._last_request_ts = time.monotonic()

        # 304 → içerik değişmemiş, boş liste + boş dict dön.
        if response.status_code == 304:
            logger.info("Kandilli 304 Not Modified — no new events")
            return [], {}

        # Yeni ETag varsa sakla, sonraki çağrıda kullan.
        new_etag = response.headers.get("ETag")
        if new_etag:
            self._etag = new_etag

        try:
            payload = response.json()
        except ValueError as e:
            logger.error(f"Kandilli JSON parse error: {e}")
            raise ValueError(f"Kandilli response is not valid JSON: {e}") from e

        if not isinstance(payload, dict) or payload.get("status") is not True:
            logger.error(f"Kandilli unexpected payload: {payload!r}")
            raise ValueError("Kandilli response status is not true")

        # API anahtarı belirsiz — hem "result" hem "results" dene (fallback).
        results = payload.get("result") or payload.get("results") or []

        events: List[EarthquakeEvent] = []
        for item in results:
            # GeoJSON coordinates: [lon, lat, optional depth]
            geojson = item.get("geojson", {}) or {}
            coords = geojson.get("coordinates", []) or []
            # Koordinat yoksa None — 0.0 Null Island (0,0) yanıltısı yaratır.
            lon = coords[0] if len(coords) > 0 else None
            lat = coords[1] if len(coords) > 1 else None
            # Derinlik item.depth veya coords[2] fallback — API'ler farklı format dönebilir.
            # `or` kullanılmaz: 0.0 (yüzey depremi) falsy'dir, fallback'e kayar ve
            # gerçekte 0.0 olan derinlik None olurdu. `is not None` ile net kontrol.
            depth_val = item.get("depth")
            depth_km = (
                depth_val
                if depth_val is not None
                else (coords[2] if len(coords) > 2 else None)
            )
            if isinstance(depth_km, (int, float)):
                depth_km = float(depth_km)

            event_time = _parse_istanbul_to_utc(item.get("date_time"))
            created_at = _parse_istanbul_to_utc(item.get("created_at"))

            # Timestamp parse edilemezse event'i atla — now() ile maskelemek
            # yanlış saat damgasıyla BQ'ya çöp veri yazmaktır.
            if event_time is None:
                logger.warning(
                    f"Skipping Kandilli event {item.get('earthquake_id')!r}: "
                    f"unparseable date_time={item.get('date_time')!r}"
                )
                continue

            event = EarthquakeEvent(
                source="kandilli",
                event_id=str(item.get("earthquake_id", "")),
                event_time=event_time,
                mag=item.get("mag"),
                depth_km=depth_km,
                lon=lon,
                lat=lat,
                place=item.get("title"),
                raw_json=item,
                created_at=created_at,
                location_tz=item.get("location_tz"),
                provider=item.get("provider"),
                epi_center_name=item.get("epi_center_name"),
                epi_center_population=item.get("epi_center_population"),
                closest_city_name=item.get("closest_city_name"),
                closest_city_distance_km=item.get("closest_city_distance_km"),
                location_properties=item.get("location_properties"),
            )
            events.append(event)

        logger.info(f"Kandilli fetched {len(events)} events")
        return events, payload
