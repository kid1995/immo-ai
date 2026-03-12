from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

from core.ports import CrawlerPort, CrawlResult


class Crawl4AIAdapter(CrawlerPort):
    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless

    async def crawl(self, url: str, **kwargs) -> CrawlResult:  # noqa: ANN003
        extraction_schema: dict | None = kwargs.get("extraction_schema")
        css_selector: str | None = kwargs.get("css_selector")
        wait_for: str | None = kwargs.get("wait_for")
        js_code: str | list[str] | None = kwargs.get("js_code")
        timeout_ms: int = kwargs.get("timeout_ms", 30_000)

        # Build CrawlerRunConfig kwargs conditionally – it doesn't accept None
        run_cfg_kwargs: dict = {"cache_mode": CacheMode.BYPASS}
        if extraction_schema is not None:
            run_cfg_kwargs["extraction_strategy"] = JsonCssExtractionStrategy(
                extraction_schema
            )
        if css_selector is not None:
            run_cfg_kwargs["css_selector"] = css_selector
        if wait_for is not None:
            run_cfg_kwargs["wait_for"] = wait_for
        if js_code is not None:
            run_cfg_kwargs["js_code"] = js_code

        run_cfg = CrawlerRunConfig(**run_cfg_kwargs)

        try:
            async with AsyncWebCrawler(
                headless=self._headless,
                timeout=timeout_ms,
            ) as crawler:
                result = await crawler.arun(url=url, config=run_cfg)  # type: ignore[union-attr]

                if not result.success:
                    return CrawlResult(
                        url=url,
                        success=False,
                        error=result.error_message or "Crawl failed",
                    )

                return CrawlResult(
                    url=url,
                    success=True,
                    html=result.html,
                    markdown=result.markdown.raw_markdown if result.markdown else None,
                    structured_data=(
                        result.extracted_content if extraction_schema else None
                    ),
                )
        except Exception as exc:
            return CrawlResult(url=url, success=False, error=str(exc))
