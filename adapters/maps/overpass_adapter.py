import math

import httpx

from core.ports import Competitor, GeoPoint

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org"

# OSM tag mapping for business categories
_CATEGORY_QUERIES: dict[str, str] = {
    "nail_studio": '["shop"="beauty"]',
    "restaurant": '["amenity"="restaurant"]',
    "imbiss": '["amenity"="fast_food"]',
    "cafe": '["amenity"="cafe"]',
    "bar": '["amenity"="bar"]',
}


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in meters between two points."""
    r = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class OverpassAdapter:
    """Implements MapPort Protocol using OSM Overpass API + Nominatim."""

    _HEADERS = {"User-Agent": "immo-ai/0.1 (commercial-real-estate-finder)"}

    async def geocode(self, address: str) -> GeoPoint | None:
        async with httpx.AsyncClient(headers=self._HEADERS, timeout=10) as client:
            response = await client.get(
                f"{_NOMINATIM_URL}/search",
                params={"q": address, "format": "json", "limit": 1},
            )
            response.raise_for_status()
            results = response.json()

        if not results:
            return None

        return GeoPoint(lat=float(results[0]["lat"]), lng=float(results[0]["lon"]))

    async def reverse_geocode(self, lat: float, lng: float) -> str | None:
        async with httpx.AsyncClient(headers=self._HEADERS, timeout=10) as client:
            response = await client.get(
                f"{_NOMINATIM_URL}/reverse",
                params={"lat": lat, "lon": lng, "format": "json"},
            )
            response.raise_for_status()
            data = response.json()

        return data.get("display_name")

    async def find_competitors(
        self,
        lat: float,
        lng: float,
        category: str,
        radius_m: int = 1000,
    ) -> list[Competitor]:
        osm_filter = _CATEGORY_QUERIES.get(category)
        if osm_filter is None:
            return []

        query = (
            f"[out:json][timeout:25];"
            f"("
            f"  node{osm_filter}(around:{radius_m},{lat},{lng});"
            f"  way{osm_filter}(around:{radius_m},{lat},{lng});"
            f");"
            f"out center;"
        )

        async with httpx.AsyncClient(headers=self._HEADERS, timeout=30) as client:
            response = await client.post(
                _OVERPASS_URL,
                data={"data": query},
            )
            response.raise_for_status()
            data = response.json()

        competitors: list[Competitor] = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            e_lat = element.get("lat") or element.get("center", {}).get("lat")
            e_lng = element.get("lon") or element.get("center", {}).get("lon")
            if e_lat is None or e_lng is None:
                continue

            competitors.append(
                Competitor(
                    name=tags.get("name", "Unknown"),
                    category=category,
                    lat=float(e_lat),
                    lng=float(e_lng),
                    distance_m=_haversine_m(lat, lng, float(e_lat), float(e_lng)),
                )
            )

        return sorted(competitors, key=lambda c: c.distance_m)
