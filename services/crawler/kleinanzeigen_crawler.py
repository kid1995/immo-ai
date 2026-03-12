"""eBay Kleinanzeigen (now Kleinanzeigen.de) listing crawler.

Crawls Gewerbeimmobilien listings including Ablöse (takeover fee) data.
"""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.models import Listing
from core.ports import CrawlerPort, LLMMessage, LLMPort

log = get_logger(__name__)

_SEARCH_URL = "https://www.kleinanzeigen.de/s-gewerbeimmobilien"
_BASE_URL = "https://www.kleinanzeigen.de"


class ExtractedKleinanzeigen(BaseModel):
    """Schema for LLM-extracted Kleinanzeigen listing data."""

    titel: str | None = None
    mietpreis: float | None = None
    ablöse: float | None = None
    kaution: float | None = None
    nebenkosten: float | None = None
    flaeche_m2: float | None = None
    etage: int | None = None
    stadt: str | None = None
    plz: str | None = None
    adresse: str | None = None
    kueche: bool | None = None
    lueftung: bool | None = None
    parkplaetze: bool | None = None
    wasseranschluss: bool | None = None
    starkstrom: bool | None = None
    beschreibung: str | None = None
    vormieter_typ: str | None = None  # Kleinanzeigen often mentions previous business


class KleinanzeigenCrawler:
    def __init__(
        self,
        *,
        crawler: CrawlerPort,
        llm: LLMPort,
        db: AsyncSession,
    ) -> None:
        self._crawler = crawler
        self._llm = llm
        self._db = db

    async def crawl_city(self, stadt: str, max_pages: int = 3) -> int:
        """Crawl Kleinanzeigen listings for a city. Returns count of upserted listings."""
        listing_urls = await self._discover_listings(stadt, max_pages)
        log.info(
            "discovered_listings",
            source="kleinanzeigen",
            stadt=stadt,
            count=len(listing_urls),
        )

        upserted = 0
        results = await self._crawler.crawl_many(listing_urls, max_concurrent=3)

        for result in results:
            if not result.success or not result.html:
                log.warning("crawl_failed", url=result.url, error=result.error)
                continue

            try:
                extracted = await self._extract_with_llm(result.html)
                await self._upsert_listing(
                    source_url=result.url,
                    extracted=extracted,
                    raw_html=result.html,
                )
                upserted += 1
            except Exception as exc:
                log.error("extraction_failed", url=result.url, error=str(exc))

        log.info(
            "crawl_complete", source="kleinanzeigen", stadt=stadt, upserted=upserted
        )
        return upserted

    async def _discover_listings(self, stadt: str, max_pages: int) -> list[str]:
        """Crawl search result pages and extract listing URLs."""
        urls: list[str] = []

        for page in range(1, max_pages + 1):
            search_url = f"{_SEARCH_URL}/c277l{stadt}/seite:{page}"
            result = await self._crawler.crawl(search_url)

            if not result.success or not result.markdown:
                log.warning("search_page_failed", page=page, error=result.error)
                break

            page_urls = self._parse_listing_urls(result.markdown)
            if not page_urls:
                break
            urls.extend(page_urls)

        return urls

    @staticmethod
    def _parse_listing_urls(markdown: str) -> list[str]:
        """Extract Kleinanzeigen listing URLs from crawled markdown."""
        urls: list[str] = []
        for line in markdown.split("\n"):
            if "/s-anzeige/" in line:
                start = line.find("/s-anzeige/")
                if start != -1:
                    end = line.find(")", start)
                    if end == -1:
                        end = line.find('"', start)
                    if end == -1:
                        end = line.find(" ", start)
                    if end == -1:
                        end = len(line)
                    path = line[start:end].strip()
                    full_url = f"{_BASE_URL}{path}"
                    if full_url not in urls:
                        urls.append(full_url)
        return urls

    async def _extract_with_llm(self, html: str) -> ExtractedKleinanzeigen:
        """Use LLM to extract structured listing data from HTML."""
        truncated = html[:15000] if len(html) > 15000 else html

        messages = [
            LLMMessage(
                role="user",
                content=(
                    "Extract the following fields from this German Kleinanzeigen "
                    "commercial real estate listing HTML. Pay special attention to "
                    "Ablöse (takeover fee) and any mention of the previous tenant type "
                    "(Nagelstudio, Restaurant, etc.).\n\n"
                    f"HTML:\n{truncated}"
                ),
            )
        ]

        result = await self._llm.complete_structured(
            messages=messages,
            output_schema=ExtractedKleinanzeigen,
            system=(
                "You are a data extraction assistant for German Kleinanzeigen listings. "
                "Extract structured fields precisely. "
                "Convert German number formats (1.234,56 → 1234.56). "
                "If Ablöse is mentioned, extract it. "
                "If the previous tenant type is mentioned, classify as: "
                "nail | restaurant | cafe | bar | retail | office | unknown"
            ),
        )

        return result  # type: ignore[return-value]

    async def _upsert_listing(
        self,
        source_url: str,
        extracted: ExtractedKleinanzeigen,
        raw_html: str,
    ) -> None:
        """Insert or update a listing in the database."""
        existing = await self._db.execute(
            select(Listing).where(
                Listing.source == "kleinanzeigen",
                Listing.source_url == source_url,
            )
        )
        listing = existing.scalar_one_or_none()

        data = extracted.model_dump(exclude_none=True)
        # Remove non-Listing fields
        vormieter_typ = data.pop("vormieter_typ", None)
        data["raw_data"] = {
            "html_length": len(raw_html),
            "vormieter_typ": vormieter_typ,
        }

        if listing:
            for field, value in data.items():
                setattr(listing, field, value)
        else:
            listing = Listing(
                source="kleinanzeigen",
                source_url=source_url,
                **data,
            )
            self._db.add(listing)

        await self._db.flush()
