from abc import ABC, abstractmethod
from typing import List, Tuple

from models import EarthquakeEvent


class BaseFetcher(ABC):
    """Tüm kaynak fetcher'larının ortak arayüzü.

    `fetch` hem normalize edilmiş event listesi hem de ham API yanıtını döner;
    ham yanıt GCS'e raw olarak yazılacak, event listesi BQ'ya transform edilecek.
    """

    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    async def fetch(self) -> Tuple[List[EarthquakeEvent], dict]:
        """API'den veriyi çek, (event listesi, ham yanıt dict) tuple'ı dön."""
        ...
