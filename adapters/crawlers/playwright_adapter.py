from playwright.async_api import async_playwright

from core.ports import CrawlerPort, CrawlResult


class PlaywrightAdapter(CrawlerPort):
    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless

    async def crawl(self, url: str, **kwargs) -> CrawlResult:  # noqa: ANN003
        wait_for: str | None = kwargs.get("wait_for")
        js_code: str | list[str] | None = kwargs.get("js_code")
        timeout_ms: int = kwargs.get("timeout_ms", 30_000)
        css_selector: str | None = kwargs.get("css_selector")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self._headless)
                page = await browser.new_page()

                await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=timeout_ms)

                if js_code:
                    scripts = js_code if isinstance(js_code, list) else [js_code]
                    for script in scripts:
                        await page.evaluate(script)

                if css_selector:
                    html = await page.inner_html(css_selector)
                else:
                    html = await page.content()

                await browser.close()

            return CrawlResult(url=url, success=True, html=html)
        except Exception as exc:
            return CrawlResult(url=url, success=False, error=str(exc))
