from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CrawlResult:
    url: str
    success: bool
    html: str | None = None
    markdown: str | None = None
    structured_data: dict | None = None
    error: str | None = None


class CrawlerPort(ABC):
    @abstractmethod
    async def crawl(self, url: str, **kwargs) -> CrawlResult: ...

    @abstractmethod
    async def crawl_many(
        self,
        urls: list[str],
        max_concurrent: int = 3,
    ) -> list[CrawlResult]: ...
