"""Pydantic schemas for API request/response – separate from ORM models."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Listing Schemas ──────────────────────────────────────────────────────────


class ListingBase(BaseModel):
    source: str
    source_id: str | None = None
    source_url: str | None = None
    mietpreis: Decimal | None = None
    ablöse: Decimal | None = None
    kaution: Decimal | None = None
    nebenkosten: Decimal | None = None
    flaeche_m2: Decimal | None = None
    etage: int | None = None
    stadt: str | None = None
    bundesland: str | None = None
    plz: str | None = None
    adresse: str | None = None
    lat: Decimal | None = None
    lng: Decimal | None = None
    kueche: bool | None = None
    lueftung: bool | None = None
    parkplaetze: bool | None = None
    wasseranschluss: bool | None = None
    starkstrom: bool | None = None
    titel: str | None = None
    beschreibung: str | None = None
    status: str = "active"


class ListingCreate(ListingBase):
    raw_data: dict | None = None


class ListingUpdate(BaseModel):
    mietpreis: Decimal | None = None
    ablöse: Decimal | None = None
    kaution: Decimal | None = None
    nebenkosten: Decimal | None = None
    flaeche_m2: Decimal | None = None
    status: str | None = None
    titel: str | None = None
    beschreibung: str | None = None


class ListingResponse(ListingBase):
    id: uuid.UUID
    first_seen: datetime
    last_seen: datetime
    raw_data: dict | None = None

    model_config = {"from_attributes": True}


# ── Score Schemas ────────────────────────────────────────────────────────────


class ScoreResponse(BaseModel):
    listing_id: uuid.UUID
    branche: str
    score_gesamt: Decimal | None = None
    score_location: Decimal | None = None
    score_financial: Decimal | None = None
    score_physical: Decimal | None = None
    score_market: Decimal | None = None
    revenue_min: Decimal | None = None
    revenue_max: Decimal | None = None
    revenue_confidence: Decimal | None = None
    explanation: dict | None = None
    calculated_at: datetime

    model_config = {"from_attributes": True}


# ── Location Intel Schemas ───────────────────────────────────────────────────


class LocationIntelResponse(BaseModel):
    plz: str
    radius_m: int
    einwohner: int | None = None
    kaufkraft_index: Decimal | None = None
    competitor_count: int | None = None
    mietspiegel: Decimal | None = None
    leerstandsquote: Decimal | None = None

    model_config = {"from_attributes": True}


# ── Search / Filter Schemas ──────────────────────────────────────────────────


class ListingFilter(BaseModel):
    stadt: str | None = None
    bundesland: str | None = None
    plz: str | None = None
    min_flaeche: Decimal | None = None
    max_flaeche: Decimal | None = None
    min_mietpreis: Decimal | None = None
    max_mietpreis: Decimal | None = None
    kueche: bool | None = None
    lueftung: bool | None = None
    wasseranschluss: bool | None = None
    starkstrom: bool | None = None
    status: str = "active"


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    branche: str | None = None


# ── Agent / Chat Schemas ────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    branche: str = "nail"  # nail | restaurant


# ── Pagination ──────────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel):
    data: list
    total: int
    page: int = 1
    limit: int = 20


class APIResponse(BaseModel):
    success: bool
    data: object | None = None
    error: str | None = None
