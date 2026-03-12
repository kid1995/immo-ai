"""CRUD + search endpoints for listings."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import db_session
from core.models import Listing
from core.schemas import (
    APIResponse,
    ListingCreate,
    ListingResponse,
    ListingUpdate,
    PaginatedResponse,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_listings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    stadt: str | None = None,
    plz: str | None = None,
    min_flaeche: float | None = None,
    max_flaeche: float | None = None,
    min_mietpreis: float | None = None,
    max_mietpreis: float | None = None,
    status: str = "active",
    db: AsyncSession = Depends(db_session),
) -> PaginatedResponse:
    query = select(Listing).where(Listing.status == status)

    if stadt:
        query = query.where(Listing.stadt == stadt)
    if plz:
        query = query.where(Listing.plz == plz)
    if min_flaeche is not None:
        query = query.where(Listing.flaeche_m2 >= min_flaeche)
    if max_flaeche is not None:
        query = query.where(Listing.flaeche_m2 <= max_flaeche)
    if min_mietpreis is not None:
        query = query.where(Listing.mietpreis >= min_mietpreis)
    if max_mietpreis is not None:
        query = query.where(Listing.mietpreis <= max_mietpreis)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Paginate
    offset = (page - 1) * limit
    results = await db.execute(
        query.order_by(Listing.last_seen.desc()).offset(offset).limit(limit)
    )
    listings = results.scalars().all()

    return PaginatedResponse(
        data=[ListingResponse.model_validate(item) for item in listings],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{listing_id}", response_model=APIResponse)
async def get_listing(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(db_session),
) -> APIResponse:
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    return APIResponse(
        success=True,
        data=ListingResponse.model_validate(listing),
    )


@router.post("", response_model=APIResponse, status_code=201)
async def create_listing(
    body: ListingCreate,
    db: AsyncSession = Depends(db_session),
) -> APIResponse:
    listing = Listing(**body.model_dump())
    db.add(listing)
    await db.flush()

    return APIResponse(
        success=True,
        data=ListingResponse.model_validate(listing),
    )


@router.patch("/{listing_id}", response_model=APIResponse)
async def update_listing(
    listing_id: uuid.UUID,
    body: ListingUpdate,
    db: AsyncSession = Depends(db_session),
) -> APIResponse:
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(listing, field, value)

    await db.flush()

    return APIResponse(
        success=True,
        data=ListingResponse.model_validate(listing),
    )


@router.delete("/{listing_id}", response_model=APIResponse)
async def delete_listing(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(db_session),
) -> APIResponse:
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Soft delete
    listing.status = "deleted"
    await db.flush()

    return APIResponse(success=True, data=None)
