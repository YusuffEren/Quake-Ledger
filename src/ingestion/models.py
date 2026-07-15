from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EarthquakeEvent:
    """USGS ve Kandilli kaynaklarını tek şemada birleştiren ortak event modeli.

    Hangi alanların doldurulduğu `source` alanına bağlıdır — her kaynak yalnızca
    kendine ait kolonları set eder, diğerleri None/varsayılan kalır.
    """
    source: str
    event_id: str
    event_time: datetime
    mag: Optional[float] = None
    depth_km: Optional[float] = None
    # 0.0 maskelemesi Null Island (0,0) yanıltısı yaratır — eksik koordinat
    # None olmalı ki downstream filtreleme mümkün olsun.
    lon: Optional[float] = None
    lat: Optional[float] = None
    place: Optional[str] = None
    raw_json: Optional[dict] = None

    # USGS'ye özgü alanlar
    updated: Optional[datetime] = None
    mag_type: Optional[str] = None
    status: Optional[str] = None
    tsunami: Optional[int] = None
    sig: Optional[int] = None
    net: Optional[str] = None
    nst: Optional[int] = None
    dmin: Optional[float] = None
    rms: Optional[float] = None
    gap: Optional[float] = None
    event_type: Optional[str] = None
    alert: Optional[str] = None
    cdi: Optional[float] = None
    mmi: Optional[float] = None
    felt: Optional[int] = None
    source_url: Optional[str] = None

    # Kandilli'ye özgü alanlar
    created_at: Optional[datetime] = None
    location_tz: Optional[str] = None
    provider: Optional[str] = None
    epi_center_name: Optional[str] = None
    epi_center_population: Optional[int] = None
    closest_city_name: Optional[str] = None
    closest_city_distance_km: Optional[float] = None
    location_properties: Optional[dict] = None