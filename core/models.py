import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

# pgvector type – registered after extension is loaded
try:
    from pgvector.sqlalchemy import Vector

    VECTOR_TYPE = Vector(1536)
except ImportError:
    # Fallback during early dev before pgvector is installed
    from sqlalchemy import Text as Vector  # type: ignore[assignment]

    VECTOR_TYPE = Text()


class Listing(Base):
    __tablename__ = "listings"

    # ── Identity ──────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(50))  # immoscout | kleinanzeigen
    source_id: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text)

    # ── Financials ────────────────────────────
    mietpreis: Mapped[float | None] = mapped_column(Numeric(10, 2))
    ablöse: Mapped[float | None] = mapped_column(Numeric(10, 2))
    kaution: Mapped[float | None] = mapped_column(Numeric(10, 2))
    nebenkosten: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # ── Physical ──────────────────────────────
    flaeche_m2: Mapped[float | None] = mapped_column(Numeric(8, 2))
    etage: Mapped[int | None] = mapped_column(SmallInteger)

    # ── Location ──────────────────────────────
    stadt: Mapped[str | None] = mapped_column(String(100))
    bundesland: Mapped[str | None] = mapped_column(String(50))
    plz: Mapped[str | None] = mapped_column(String(10))
    adresse: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    lng: Mapped[float | None] = mapped_column(Numeric(10, 7))

    # ── Features ──────────────────────────────
    kueche: Mapped[bool | None] = mapped_column(Boolean)
    lueftung: Mapped[bool | None] = mapped_column(Boolean)
    parkplaetze: Mapped[bool | None] = mapped_column(Boolean)
    wasseranschluss: Mapped[bool | None] = mapped_column(Boolean)
    starkstrom: Mapped[bool | None] = mapped_column(Boolean)

    # ── Content ───────────────────────────────
    titel: Mapped[str | None] = mapped_column(Text)
    beschreibung: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(VECTOR_TYPE)

    # ── Meta ──────────────────────────────────
    status: Mapped[str] = mapped_column(String(20), default="active")
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ─────────────────────────
    scores: Mapped[list["ListingScore"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class LocationIntel(Base):
    __tablename__ = "location_intel"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plz: Mapped[str] = mapped_column(String(10), index=True)
    radius_m: Mapped[int] = mapped_column(Integer, default=1000)

    # ── Demographics ──────────────────────────
    einwohner: Mapped[int | None] = mapped_column(Integer)
    einwohner_dichte: Mapped[float | None] = mapped_column(Numeric(10, 2))
    kaufkraft_index: Mapped[float | None] = mapped_column(Numeric(6, 2))  # 100 = DE avg
    altersstruktur: Mapped[dict | None] = mapped_column(JSONB)

    # ── Competitors ───────────────────────────
    competitors: Mapped[list | None] = mapped_column(
        JSONB
    )  # [{name, category, distance_m, rating}]
    competitor_count: Mapped[int | None] = mapped_column(Integer)

    # ── Economics ─────────────────────────────
    mietspiegel: Mapped[float | None] = mapped_column(Numeric(8, 2))  # avg €/m²
    leerstandsquote: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # ── Previous tenant ───────────────────────
    vormieter_typ: Mapped[str | None] = mapped_column(String(50))
    vormieter_data: Mapped[dict | None] = mapped_column(JSONB)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ListingScore(Base):
    __tablename__ = "listing_scores"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), primary_key=True
    )
    branche: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # nail | restaurant

    # ── Scores (0.0 – 10.0) ───────────────────
    score_gesamt: Mapped[float | None] = mapped_column(Numeric(4, 2))
    score_location: Mapped[float | None] = mapped_column(Numeric(4, 2))
    score_financial: Mapped[float | None] = mapped_column(Numeric(4, 2))
    score_physical: Mapped[float | None] = mapped_column(Numeric(4, 2))
    score_market: Mapped[float | None] = mapped_column(Numeric(4, 2))

    # ── Revenue estimate ──────────────────────
    revenue_min: Mapped[float | None] = mapped_column(Numeric(10, 2))
    revenue_max: Mapped[float | None] = mapped_column(Numeric(10, 2))
    revenue_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))  # 0.0 – 1.0

    explanation: Mapped[dict | None] = mapped_column(JSONB)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ─────────────────────────
    listing: Mapped["Listing"] = relationship(back_populates="scores")
