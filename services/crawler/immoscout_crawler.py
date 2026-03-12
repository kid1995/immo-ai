"""ImmobilienScout24 listing crawler.

Crawls search results pages to discover listing URLs,
then crawls each detail page with LLM extraction.
"""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.models import Listing
from core.ports import CrawlerPort, LLMMessage, LLMPort

log = get_logger(__name__)

_SEARCH_URL = "https://www.immobilienscout24.de/Suche/de/gewerbeimmobilien/mieten"
_BASE_URL = "https://www.immobilienscout24.de"


class ExtractedListing(BaseModel):
    """Schema for LLM-extracted listing data."""

    titel: str | None = None
    mietpreis: float | None = None
    ablöse: float | None = None
    kaution: float | None = None
    nebenkosten: float | None = None
    flaeche_m2: float | None = None
    etage: int | None = None
    stadt: str | None = None
    bundesland: str | None = None
    plz: str | None = None
    adresse: str | None = None
    kueche: bool | None = None
    lueftung: bool | None = None
    parkplaetze: bool | None = None
    wasseranschluss: bool | None = None
    starkstrom: bool | None = None
    beschreibung: str | None = None


class ImmoscoutCrawler:
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
        """Crawl listings for a city. Returns count of upserted listings."""
        listing_urls = await self._discover_listings(stadt, max_pages)
        log.info("discovered_listings", stadt=stadt, count=len(listing_urls))

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

        log.info("crawl_complete", stadt=stadt, upserted=upserted)
        return upserted

    async def _discover_listings(self, stadt: str, max_pages: int) -> list[str]:
        """Crawl search result pages and extract listing URLs."""
        urls: list[str] = []

        for page in range(1, max_pages + 1):
            search_url = f"{_SEARCH_URL}?pagenumber={page}&geocodes=de_{stadt.lower()}"
            result = await self._crawler.crawl(search_url)

            if not result.success or not result.markdown:
                log.warning("search_page_failed", page=page, error=result.error)
                break

            # Extract listing URLs from markdown
            page_urls = self._parse_listing_urls(result.markdown)
            if not page_urls:
                break
            urls.extend(page_urls)

        return urls

    @staticmethod
    def _parse_listing_urls(markdown: str) -> list[str]:
        """Extract immoscout listing URLs from crawled markdown."""
        urls: list[str] = []
        for line in markdown.split("\n"):
            if "/expose/" in line:
                start = line.find("/expose/")
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

    async def _extract_with_llm(self, html: str) -> ExtractedListing:
        """Use LLM to extract structured listing data from HTML."""
        # Truncate HTML to avoid token limits
        truncated = html[:15000] if len(html) > 15000 else html

        messages = [
            LLMMessage(
                role="user",
                content=(
                    "Extract the following fields from this German commercial real estate listing HTML. "
                    "Return structured data.\n\n"
                    f"HTML:\n{truncated}"
                ),
            )
        ]

        result = await self._llm.complete_structured(
            messages=messages,
            output_schema=ExtractedListing,
            system=(
                "You are a data extraction assistant. Extract structured fields from "
                "German commercial real estate (Gewerbeimmobilien) listings. "
                "Be precise with numbers. Convert German number formats (1.234,56 → 1234.56)."
            ),
        )

        return result  # type: ignore[return-value]

    async def _upsert_listing(
        self,
        source_url: str,
        extracted: ExtractedListing,
        raw_html: str,
    ) -> None:
        """Insert or update a listing in the database."""
        # Check if listing already exists by source_url
        existing = await self._db.execute(
            select(Listing).where(
                Listing.source == "immoscout",
                Listing.source_url == source_url,
            )
        )
        listing = existing.scalar_one_or_none()

        data = extracted.model_dump(exclude_none=True)
        data["raw_data"] = {"html_length": len(raw_html)}

        if listing:
            # Update existing
            for field, value in data.items():
                setattr(listing, field, value)
        else:
            # Create new
            listing = Listing(
                source="immoscout",
                source_url=source_url,
                **data,
            )
            self._db.add(listing)

        await self._db.flush()
