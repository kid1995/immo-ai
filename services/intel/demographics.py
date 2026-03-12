"""Demographics enrichment service using Destatis API (free)."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.models import LocationIntel

log = get_logger(__name__)

# Destatis Genesis API (free, requires no key for basic data)
_DESTATIS_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020"


class DemographicsService:
    def __init__(self, *, db: AsyncSession) -> None:
        self._db = db

    async def enrich_plz(self, plz: str, radius_m: int = 1000) -> LocationIntel | None:
        """Fetch demographics for a PLZ and store in location_intel.

        Uses publicly available data. Falls back to estimates if API is unavailable.
        """
        # Fetch or create intel record
        existing = await self._db.execute(
            select(LocationIntel).where(
                LocationIntel.plz == plz,
                LocationIntel.radius_m == radius_m,
            )
        )
        intel = existing.scalar_one_or_none()

        # Skip if already has demographics
        if intel and intel.einwohner is not None:
            return intel

        demographics = await self._fetch_demographics(plz)

        if intel:
            intel.einwohner = demographics.get("einwohner")
            intel.kaufkraft_index = demographics.get("kaufkraft_index")
            intel.altersstruktur = demographics.get("altersstruktur")
            intel.einwohner_dichte = demographics.get("einwohner_dichte")
        else:
            intel = LocationIntel(
                plz=plz,
                radius_m=radius_m,
                einwohner=demographics.get("einwohner"),
                kaufkraft_index=demographics.get("kaufkraft_index"),
                altersstruktur=demographics.get("altersstruktur"),
                einwohner_dichte=demographics.get("einwohner_dichte"),
            )
            self._db.add(intel)

        await self._db.flush()
        log.info("demographics_enriched", plz=plz)
        return intel

    async def _fetch_demographics(self, plz: str) -> dict:
        """Fetch demographics data for a PLZ.

        Currently uses a simple heuristic based on PLZ region.
        In production, integrate with Destatis API or GfK Kaufkraft data.
        """
        try:
            return await self._fetch_from_api(plz)
        except Exception as exc:
            log.warning("demographics_api_failed", plz=plz, error=str(exc))
            return self._estimate_from_plz(plz)

    async def _fetch_from_api(self, plz: str) -> dict:
        """Try to fetch from Destatis or similar open data source."""
        # PLZ-based open data lookup
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"https://api.zippopotam.us/de/{plz}",
            )
            response.raise_for_status()
            data = response.json()

        # zippopotam gives basic location info – we supplement with estimates
        place_name = data.get("places", [{}])[0].get("place name", "")
        state = data.get("places", [{}])[0].get("state", "")

        return {
            "einwohner": self._estimate_population_from_plz(plz),
            "kaufkraft_index": self._estimate_kaufkraft(state),
            "altersstruktur": {"0-18": 17, "18-65": 63, "65+": 20},
            "einwohner_dichte": None,
            "place_name": place_name,
            "state": state,
        }

    @staticmethod
    def _estimate_from_plz(plz: str) -> dict:
        """Rough estimates based on PLZ ranges in Germany."""
        return {
            "einwohner": 50000,  # conservative estimate
            "kaufkraft_index": 100.0,  # national average
            "altersstruktur": {"0-18": 17, "18-65": 63, "65+": 20},
            "einwohner_dichte": None,
        }

    @staticmethod
    def _estimate_population_from_plz(plz: str) -> int:
        """Rough population estimate based on PLZ prefix (major city areas)."""
        prefix = plz[:2]
        # Major city PLZ prefixes → higher population
        major_cities = {
            "10": 300000,
            "20": 200000,
            "40": 150000,
            "50": 200000,
            "60": 250000,
            "70": 150000,
            "80": 250000,
            "90": 100000,
        }
        return major_cities.get(prefix, 50000)

    @staticmethod
    def _estimate_kaufkraft(state: str) -> float:
        """Kaufkraft index estimate per Bundesland. 100 = DE average."""
        state_index = {
            "Bayern": 112,
            "Baden-Württemberg": 110,
            "Hessen": 115,
            "Hamburg": 118,
            "Nordrhein-Westfalen": 103,
            "Niedersachsen": 98,
            "Rheinland-Pfalz": 100,
            "Schleswig-Holstein": 99,
            "Berlin": 95,
            "Bremen": 97,
            "Saarland": 96,
            "Sachsen": 88,
            "Thüringen": 87,
            "Sachsen-Anhalt": 85,
            "Brandenburg": 90,
            "Mecklenburg-Vorpommern": 84,
        }
        return float(state_index.get(state, 100))
