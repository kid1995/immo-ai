"""Intel enrichment worker – enriches new listings with location data."""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from core.config import settings
from core.database import AsyncSessionFactory
from core.di_container import get_map
from core.logging import get_logger, setup_logging
from core.models import Listing, LocationIntel
from services.intel.competitors import CompetitorService
from services.intel.demographics import DemographicsService

log = get_logger(__name__)


async def enrich_job() -> None:
    """Find listings missing intel and enrich them."""
    log.info("enrich_job_started")

    map_port = get_map()
    enriched_count = 0

    async with AsyncSessionFactory() as db:
        # Find active listings whose PLZ doesn't have location_intel yet
        existing_plzs = select(LocationIntel.plz).distinct()
        listings_query = (
            select(Listing)
            .where(
                Listing.status == "active",
                Listing.plz.isnot(None),
                Listing.plz.notin_(existing_plzs),
            )
            .limit(50)  # batch size
        )

        result = await db.execute(listings_query)
        listings = result.scalars().all()

        if not listings:
            log.info("no_listings_to_enrich")
            return

        competitor_service = CompetitorService(map_port=map_port, db=db)
        demographics_service = DemographicsService(db=db)

        # Track which PLZs we've already processed in this batch
        processed_plzs: set[str] = set()

        for listing in listings:
            plz = listing.plz
            if not plz or plz in processed_plzs:
                continue

            try:
                # Enrich competitors
                await competitor_service.enrich_listing(listing)

                # Enrich demographics
                await demographics_service.enrich_plz(plz)

                processed_plzs.add(plz)
                enriched_count += 1
            except Exception as exc:
                log.error("enrich_error", plz=plz, error=str(exc))

        await db.commit()

    log.info("enrich_job_complete", enriched=enriched_count)


def main() -> None:
    """Entry point: run once immediately, then schedule recurring."""
    setup_logging()
    log.info("intel_worker_starting")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        enrich_job,
        trigger=IntervalTrigger(hours=settings.crawl_interval_hours),
        id="enrich_job",
        name="Enrich listings with location intel",
        replace_existing=True,
    )

    loop = asyncio.new_event_loop()

    # Run once immediately
    loop.run_until_complete(enrich_job())

    # Then schedule recurring
    scheduler.start()
    log.info("scheduler_started")

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("intel_worker_stopped")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
