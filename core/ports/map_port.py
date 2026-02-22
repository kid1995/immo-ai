from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GeoPoint:
    lat: float
    lng: float


@dataclass
class Competitor:
    name: str
    category: str  # "nail_studio" | "restaurant" | "imbiss"
    lat: float
    lng: float
    distance_m: float
    rating: float | None = None
    review_count: int | None = None


class MapPort(ABC):
    @abstractmethod
    async def geocode(self, address: str) -> GeoPoint | None: ...

    @abstractmethod
    async def reverse_geocode(self, lat: float, lng: float) -> str | None: ...

    @abstractmethod
    async def find_competitors(
        self,
        lat: float,
        lng: float,
        category: str,
        radius_m: int = 1000,
    ) -> list[Competitor]: ...
