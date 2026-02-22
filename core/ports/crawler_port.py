import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CrawlResult:
    url: str
    success: bool
    html: str | None = None
    markdown: str | None = None
    structured_data: dict | None = None
    error: str | None = None


class CrawlerPort(ABC):
    """
    ABC (not Protocol) because crawl_many provides a shared default
    implementation that all adapters inherit for free.
    Only crawl() needs to be implemented per adapter.
    """

    @abstractmethod
    async def crawl(self, url: str, **kwargs) -> CrawlResult: ...

    async def crawl_many(
        self,
        urls: list[str],
        max_concurrent: int = 3,
    ) -> list[CrawlResult]:
        """Default concurrent implementation – adapters can override if needed."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _limited(url: str) -> CrawlResult:
            async with semaphore:
                return await self.crawl(url)

        return list(await asyncio.gather(*[_limited(u) for u in urls]))
