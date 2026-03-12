import httpx

from core.ports import Competitor, GeoPoint

_MAPS_BASE = "https://maps.googleapis.com/maps/api"

# Google Places type mapping
_CATEGORY_TYPES: dict[str, str] = {
    "nail_studio": "beauty_salon",
    "restaurant": "restaurant",
    "imbiss": "meal_takeaway",
    "cafe": "cafe",
    "bar": "bar",
}


class GoogleMapsAdapter:
    """Implements MapPort Protocol using Google Maps APIs."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def geocode(self, address: str) -> GeoPoint | None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{_MAPS_BASE}/geocode/json",
                params={"address": address, "key": self._api_key},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        if not results:
            return None

        location = results[0]["geometry"]["location"]
        return GeoPoint(lat=location["lat"], lng=location["lng"])

    async def reverse_geocode(self, lat: float, lng: float) -> str | None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{_MAPS_BASE}/geocode/json",
                params={"latlng": f"{lat},{lng}", "key": self._api_key},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        if not results:
            return None

        return results[0].get("formatted_address")

    async def find_competitors(
        self,
        lat: float,
        lng: float,
        category: str,
        radius_m: int = 1000,
    ) -> list[Competitor]:
        place_type = _CATEGORY_TYPES.get(category)
        if place_type is None:
            return []

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{_MAPS_BASE}/place/nearbysearch/json",
                params={
                    "location": f"{lat},{lng}",
                    "radius": radius_m,
                    "type": place_type,
                    "key": self._api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

        competitors: list[Competitor] = []
        for place in data.get("results", []):
            loc = place["geometry"]["location"]
            competitors.append(
                Competitor(
                    name=place.get("name", "Unknown"),
                    category=category,
                    lat=loc["lat"],
                    lng=loc["lng"],
                    distance_m=0.0,  # Google doesn't return distance directly
                    rating=place.get("rating"),
                    review_count=place.get("user_ratings_total"),
                )
            )

        return competitors
