"""Competitor analysis service using MapPort."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.models import Listing, LocationIntel
from core.ports import MapPort

log = get_logger(__name__)


class CompetitorService:
    def __init__(self, *, map_port: MapPort, db: AsyncSession) -> None:
        self._map = map_port
        self._db = db

    async def enrich_listing(
        self,
        listing: Listing,
        categories: list[str] | None = None,
        radius_m: int = 1000,
    ) -> LocationIntel | None:
        """Find competitors near a listing and store in location_intel."""
        if not listing.lat or not listing.lng:
            # Try to geocode from address
            if not listing.adresse and not listing.plz:
                log.warning("no_location_data", listing_id=str(listing.id))
                return None

            address = f"{listing.adresse or ''} {listing.plz or ''} {listing.stadt or ''} Deutschland"
            point = await self._map.geocode(address.strip())
            if not point:
                log.warning("geocode_failed", address=address)
                return None

            lat, lng = point.lat, point.lng
        else:
            lat, lng = float(listing.lat), float(listing.lng)

        if categories is None:
            categories = ["nail_studio", "restaurant"]

        all_competitors: list[dict] = []
        for category in categories:
            competitors = await self._map.find_competitors(
                lat=lat, lng=lng, category=category, radius_m=radius_m
            )
            for c in competitors:
                all_competitors.append(
                    {
                        "name": c.name,
                        "category": c.category,
                        "distance_m": round(c.distance_m, 1),
                        "lat": c.lat,
                        "lng": c.lng,
                        "rating": c.rating,
                        "review_count": c.review_count,
                    }
                )

        # Upsert into location_intel
        plz = listing.plz or "unknown"
        existing = await self._db.execute(
            select(LocationIntel).where(
                LocationIntel.plz == plz,
                LocationIntel.radius_m == radius_m,
            )
        )
        intel = existing.scalar_one_or_none()

        if intel:
            intel.competitors = all_competitors
            intel.competitor_count = len(all_competitors)
        else:
            intel = LocationIntel(
                plz=plz,
                radius_m=radius_m,
                competitors=all_competitors,
                competitor_count=len(all_competitors),
            )
            self._db.add(intel)

        await self._db.flush()
        log.info("competitors_enriched", plz=plz, count=len(all_competitors))
        return intel
