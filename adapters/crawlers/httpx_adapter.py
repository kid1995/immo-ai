import httpx

from core.ports import CrawlerPort, CrawlResult


class HttpxAdapter(CrawlerPort):
    """Lightweight adapter for static pages – no JS rendering."""

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }

    async def crawl(self, url: str, **kwargs) -> CrawlResult:  # noqa: ANN003
        timeout_ms: int = kwargs.get("timeout_ms", 30_000)

        try:
            async with httpx.AsyncClient(
                headers=self._HEADERS,
                follow_redirects=True,
                timeout=timeout_ms / 1000,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            return CrawlResult(
                url=url,
                success=True,
                html=response.text,
            )
        except Exception as exc:
            return CrawlResult(url=url, success=False, error=str(exc))
