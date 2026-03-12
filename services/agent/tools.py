"""LangChain tool definitions for the AI search agent."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Listing, ListingScore, LocationIntel


async def search_listings(
    db: AsyncSession,
    *,
    stadt: str | None = None,
    plz: str | None = None,
    min_flaeche: float | None = None,
    max_mietpreis: float | None = None,
    branche: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """SQL-based search for listings with optional filters."""
    query = select(Listing).where(Listing.status == "active")

    if stadt:
        query = query.where(Listing.stadt.ilike(f"%{stadt}%"))
    if plz:
        query = query.where(Listing.plz == plz)
    if min_flaeche is not None:
        query = query.where(Listing.flaeche_m2 >= min_flaeche)
    if max_mietpreis is not None:
        query = query.where(Listing.mietpreis <= max_mietpreis)

    query = query.order_by(Listing.last_seen.desc()).limit(limit)
    results = await db.execute(query)
    listings = results.scalars().all()

    output: list[dict] = []
    for listing in listings:
        entry = {
            "id": str(listing.id),
            "titel": listing.titel,
            "stadt": listing.stadt,
            "plz": listing.plz,
            "mietpreis": float(listing.mietpreis) if listing.mietpreis else None,
            "flaeche_m2": float(listing.flaeche_m2) if listing.flaeche_m2 else None,
            "adresse": listing.adresse,
            "source_url": listing.source_url,
        }

        # Attach scores if branche is specified
        if branche:
            score_result = await db.execute(
                select(ListingScore).where(
                    ListingScore.listing_id == listing.id,
                    ListingScore.branche == branche,
                )
            )
            score = score_result.scalar_one_or_none()
            if score:
                entry["score_gesamt"] = (
                    float(score.score_gesamt) if score.score_gesamt else None
                )
                entry["explanation"] = score.explanation

        output.append(entry)

    return output


async def semantic_search(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    limit: int = 10,
) -> list[dict]:
    """Vector similarity search using pgvector cosine distance."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text(
        """
        SELECT id, titel, stadt, plz, mietpreis, flaeche_m2, adresse, source_url,
               embedding <=> :embedding::vector AS distance
        FROM listings
        WHERE status = 'active' AND embedding IS NOT NULL
        ORDER BY embedding <=> :embedding::vector
        LIMIT :limit
        """
    )

    results = await db.execute(sql, {"embedding": embedding_str, "limit": limit})
    rows = results.mappings().all()

    return [
        {
            "id": str(row["id"]),
            "titel": row["titel"],
            "stadt": row["stadt"],
            "plz": row["plz"],
            "mietpreis": float(row["mietpreis"]) if row["mietpreis"] else None,
            "flaeche_m2": float(row["flaeche_m2"]) if row["flaeche_m2"] else None,
            "adresse": row["adresse"],
            "source_url": row["source_url"],
            "distance": float(row["distance"]),
        }
        for row in rows
    ]


async def get_scores(
    db: AsyncSession,
    *,
    listing_id: str,
    branche: str | None = None,
) -> list[dict]:
    """Get scores for a listing."""
    query = select(ListingScore).where(
        ListingScore.listing_id == listing_id,
    )
    if branche:
        query = query.where(ListingScore.branche == branche)

    results = await db.execute(query)
    scores = results.scalars().all()

    return [
        {
            "branche": s.branche,
            "score_gesamt": float(s.score_gesamt) if s.score_gesamt else None,
            "score_location": float(s.score_location) if s.score_location else None,
            "score_financial": float(s.score_financial) if s.score_financial else None,
            "score_physical": float(s.score_physical) if s.score_physical else None,
            "score_market": float(s.score_market) if s.score_market else None,
            "revenue_min": float(s.revenue_min) if s.revenue_min else None,
            "revenue_max": float(s.revenue_max) if s.revenue_max else None,
            "explanation": s.explanation,
        }
        for s in scores
    ]


async def get_competitors(
    db: AsyncSession,
    *,
    plz: str,
) -> dict | None:
    """Get competitor data for a PLZ."""
    result = await db.execute(select(LocationIntel).where(LocationIntel.plz == plz))
    intel = result.scalar_one_or_none()

    if not intel:
        return None

    return {
        "plz": intel.plz,
        "competitor_count": intel.competitor_count,
        "competitors": intel.competitors,
        "kaufkraft_index": float(intel.kaufkraft_index)
        if intel.kaufkraft_index
        else None,
        "mietspiegel": float(intel.mietspiegel) if intel.mietspiegel else None,
    }
