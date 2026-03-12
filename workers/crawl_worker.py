"""APScheduler-based crawl worker – runs every N hours."""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.database import AsyncSessionFactory
from core.di_container import get_crawler, get_llm
from core.logging import get_logger, setup_logging
from services.crawler.immoscout_crawler import ImmoscoutCrawler
from services.crawler.kleinanzeigen_crawler import KleinanzeigenCrawler

log = get_logger(__name__)

# Cities to crawl
TARGET_CITIES = [
    "Berlin",
    "Hamburg",
    "München",
    "Köln",
    "Frankfurt",
    "Stuttgart",
    "Düsseldorf",
    "Dortmund",
    "Essen",
    "Leipzig",
]


async def crawl_job() -> None:
    """Single crawl run across all target cities and sources."""
    log.info("crawl_job_started")
    crawler = get_crawler()
    llm = get_llm()

    total_immoscout = 0
    total_kleinanzeigen = 0

    async with AsyncSessionFactory() as db:
        for city in TARGET_CITIES:
            try:
                immoscout = ImmoscoutCrawler(crawler=crawler, llm=llm, db=db)
                count = await immoscout.crawl_city(city, max_pages=2)
                total_immoscout += count
            except Exception as exc:
                log.error("immoscout_crawl_error", city=city, error=str(exc))

            try:
                kleinanzeigen = KleinanzeigenCrawler(crawler=crawler, llm=llm, db=db)
                count = await kleinanzeigen.crawl_city(city, max_pages=2)
                total_kleinanzeigen += count
            except Exception as exc:
                log.error("kleinanzeigen_crawl_error", city=city, error=str(exc))

        await db.commit()

    log.info(
        "crawl_job_complete",
        immoscout=total_immoscout,
        kleinanzeigen=total_kleinanzeigen,
    )


def main() -> None:
    """Entry point: run once immediately, then schedule recurring."""
    setup_logging()
    log.info("crawl_worker_starting", interval_hours=settings.crawl_interval_hours)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        crawl_job,
        trigger=IntervalTrigger(hours=settings.crawl_interval_hours),
        id="crawl_job",
        name="Crawl all sources",
        replace_existing=True,
    )

    loop = asyncio.new_event_loop()

    # Run once immediately
    loop.run_until_complete(crawl_job())

    # Then schedule recurring
    scheduler.start()
    log.info("scheduler_started")

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("crawl_worker_stopped")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
