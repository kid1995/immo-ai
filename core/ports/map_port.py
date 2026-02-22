from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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


@runtime_checkable
class MapPort(Protocol):
    async def geocode(self, address: str) -> GeoPoint | None: ...

    async def reverse_geocode(self, lat: float, lng: float) -> str | None: ...

    async def find_competitors(
        self,
        lat: float,
        lng: float,
        category: str,
        radius_m: int = 1000,
    ) -> list[Competitor]: ...
