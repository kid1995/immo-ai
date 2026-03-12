"""Scoring + location intelligence endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import db_session
from core.models import Listing, ListingScore, LocationIntel
from core.schemas import APIResponse, LocationIntelResponse, ScoreResponse
from services.scoring.nail_scorer import NailScorer
from services.scoring.restaurant_scorer import RestaurantScorer

router = APIRouter()


@router.get("/scores/{listing_id}", response_model=APIResponse)
async def get_scores(
    listing_id: uuid.UUID,
    branche: str | None = None,
    db: AsyncSession = Depends(db_session),
) -> APIResponse:
    query = select(ListingScore).where(ListingScore.listing_id == listing_id)
    if branche:
        query = query.where(ListingScore.branche == branche)

    results = await db.execute(query)
    scores = results.scalars().all()

    return APIResponse(
        success=True,
        data=[ScoreResponse.model_validate(s) for s in scores],
    )


@router.post("/scores/{listing_id}/calculate", response_model=APIResponse)
async def calculate_scores(
    listing_id: uuid.UUID,
    branche: str = Query(..., pattern="^(nail|restaurant)$"),
    db: AsyncSession = Depends(db_session),
) -> APIResponse:
    # Fetch listing
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Fetch location intel if available
    intel = None
    if listing.plz:
        intel_result = await db.execute(
            select(LocationIntel).where(LocationIntel.plz == listing.plz)
        )
        intel = intel_result.scalar_one_or_none()

    # Score
    scorer = NailScorer() if branche == "nail" else RestaurantScorer()
    score = scorer.score(listing, intel)

    # Upsert score
    existing = await db.execute(
        select(ListingScore).where(
            ListingScore.listing_id == listing_id,
            ListingScore.branche == branche,
        )
    )
    existing_score = existing.scalar_one_or_none()

    if existing_score:
        for field, value in score.items():
            setattr(existing_score, field, value)
    else:
        db.add(ListingScore(listing_id=listing_id, branche=branche, **score))

    await db.flush()

    return APIResponse(success=True, data=score)


@router.get("/intel/{plz}", response_model=APIResponse)
async def get_location_intel(
    plz: str,
    db: AsyncSession = Depends(db_session),
) -> APIResponse:
    result = await db.execute(select(LocationIntel).where(LocationIntel.plz == plz))
    intel = result.scalar_one_or_none()

    if intel is None:
        raise HTTPException(status_code=404, detail="No intel for this PLZ")

    return APIResponse(
        success=True,
        data=LocationIntelResponse.model_validate(intel),
    )
