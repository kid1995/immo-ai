# CLAUDE.md – immo-ai Project Context

> This file is the single source of truth for Claude Code to understand the
> current state of the project, all decisions made, and what remains to be done.

---

## What is immo-ai?

AI-powered commercial real estate finder for Vietnamese business owners in Germany.
Automatically crawls listings, enriches them with location intelligence, scores
them per business type, and provides an AI chat assistant in Vietnamese.

**Target users:** Vietnamese nail studio and restaurant owners looking for commercial
spaces (Gewerberäume) in Germany.

**Core value:** User types in Vietnamese → system finds ranked listings with
explanations in Vietnamese, based on crawled German platforms.

---

## Two Core Use Cases

### UC1 – Market Intelligence Pipeline (background, automated)

```
APScheduler (every 6h)
  → immoscout_crawler + kleinanzeigen_crawler   (Crawl4AI)
  → LLM extracts structured fields from HTML    (Claude API)
  → OpenAI embeds beschreibung                  (pgvector)
  → Overpass API fetches competitors in 500m    (OSM, free)
  → Destatis API fetches demographics per PLZ   (free)
  → nail_scorer / restaurant_scorer calculates score 0–10
  → Writes: listings, location_intel, listing_scores tables
```

### UC2 – AI Search Assistant (on demand, user triggered)

```
User types Vietnamese query in Next.js
  → FastAPI /api/agent SSE endpoint
  → LangChain agent parses intent via Claude API
  → Tools: search_listings (SQL), semantic_search (pgvector), get_scores, get_competitors
  → OpenAI embeds query → cosine distance search
  → Claude synthesizes ranked results → streams Vietnamese response
  → Next.js renders results + Mapbox map pins
```

**Key relationship:** UC1 is the producer, UC2 is the consumer. Both share the
same PostgreSQL database. UC2 quality depends entirely on how much data UC1 has
collected.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI + Python 3.12 | Async native, AI/crawling ecosystem |
| Frontend | Next.js 15 | Vercel AI SDK for SSE streaming |
| Crawling | Crawl4AI (primary), Playwright (fallback), httpx (static) | AI extraction, JS rendering |
| AI/LLM | Claude API via LangChain | Best multilingual (Vietnamese/German) |
| Embeddings | OpenAI text-embedding-3-small (1536 dims) | Semantic search |
| Database | PostgreSQL + pgvector + PostGIS | One DB for SQL + vector + geo |
| Cache/Queue | Redis + arq | Job queue, rate limiting |
| Scheduling | APScheduler 3.x | Trigger crawl jobs |
| Package mgr | uv | 100x faster than pip |
| Task runner | just | Replaces Makefile |

**Why PostgreSQL over Vector DB (Pinecone) or Graph DB (Neo4j):**
- pgvector handles semantic search
- PostGIS handles geo queries
- SQL handles filtering, joining, sorting
- One service, one backup, one bill
- 200k listings max → pgvector is more than sufficient

---

## Architecture – Ports & Adapters (Hexagonal)

All external dependencies are abstracted behind interfaces in `core/ports/`.
Swap providers by changing a single `.env` variable — zero code changes.

```
core/ports/           ← Interfaces only, no implementation
adapters/crawlers/    ← crawl4ai_adapter, playwright_adapter, httpx_adapter
adapters/llm/         ← anthropic_adapter, openai_adapter, ollama_adapter
adapters/maps/        ← overpass_adapter, google_maps_adapter
adapters/embeddings/  ← openai_embedding, local_embedding
```

**Design decision – ABC vs Protocol:**
- `CrawlerPort` uses **ABC** because `crawl_many()` has a shared default
  implementation (semaphore-based concurrency) that all adapters inherit for free.
- `LLMPort`, `MapPort`, `EmbeddingPort` use **Protocol** (structural subtyping)
  because they have no shared logic. Adapters don't need to import from core.

```python
# Swap example – zero code changes
LLM_PROVIDER=anthropic   # → uses AnthropicAdapter
LLM_PROVIDER=openai      # → uses OpenAIAdapter
CRAWLER_PROVIDER=crawl4ai
CRAWLER_PROVIDER=playwright
```

---

## Project Structure

```
immo-ai/
├── apps/
│   ├── api/
│   │   ├── main.py               # FastAPI entry point
│   │   ├── dependencies.py       # get_crawler(), get_llm() DI
│   │   └── routers/
│   │       ├── listings.py       # CRUD + search endpoints
│   │       ├── analysis.py       # scoring + intel endpoints
│   │       └── agent.py          # AI chat SSE endpoint
│   └── web/                      # Next.js 15
│
├── core/
│   ├── config.py                 # pydantic-settings, reads .env
│   ├── database.py               # SQLAlchemy async engine + get_db()
│   ├── models.py                 # ORM: Listing, LocationIntel, ListingScore
│   ├── container.py              # Adapter factory with @lru_cache
│   └── ports/
│       ├── crawler_port.py       # CrawlOptions, CrawlResult, CrawlerPort (ABC)
│       ├── llm_port.py           # LLMMessage, LLMResponse, LLMPort (Protocol)
│       ├── map_port.py           # GeoPoint, Competitor, MapPort (Protocol)
│       └── embedding_port.py     # EmbeddingPort (Protocol)
│
├── adapters/
│   ├── crawlers/
│   │   ├── crawl4ai_adapter.py   ✅ DONE
│   │   ├── playwright_adapter.py ✅ DONE
│   │   └── httpx_adapter.py      ✅ DONE
│   ├── llm/
│   │   ├── anthropic_adapter.py  ❌ TODO
│   │   ├── openai_adapter.py     ❌ TODO
│   │   └── ollama_adapter.py     ❌ TODO
│   ├── maps/
│   │   ├── overpass_adapter.py   ❌ TODO
│   │   └── google_maps_adapter.py ❌ TODO
│   └── embeddings/
│       ├── openai_embedding.py   ❌ TODO
│       └── local_embedding.py    ❌ TODO
│
├── services/
│   ├── crawler/
│   │   ├── immoscout_crawler.py  ❌ TODO
│   │   └── kleinanzeigen_crawler.py ❌ TODO
│   ├── intel/
│   │   ├── competitors.py        ❌ TODO
│   │   ├── demographics.py       ❌ TODO
│   │   └── revenue_estimator.py  ❌ TODO
│   ├── scoring/
│   │   ├── base_scorer.py        ❌ TODO
│   │   ├── nail_scorer.py        ❌ TODO
│   │   ├── restaurant_scorer.py  ❌ TODO
│   │   └── weights.py            ❌ TODO
│   └── agent/
│       ├── tools.py              ❌ TODO
│       └── agent.py              ❌ TODO
│
├── workers/
│   ├── crawl_worker.py           ❌ TODO
│   └── intel_worker.py           ❌ TODO
│
└── infra/
    └── init.sql                  ✅ DONE (pgvector, postgis, uuid-ossp, pg_trgm)
```

---

## Database Schema

### `listings` – raw crawled data

```python
class Listing(Base):
    # Identity
    id: UUID, source: str, source_id: str, source_url: str

    # Financials
    mietpreis: Decimal      # monthly rent €
    ablöse: Decimal         # takeover fee
    kaution: Decimal        # deposit (usually 3x rent)
    nebenkosten: Decimal    # utilities

    # Physical
    flaeche_m2: Decimal
    etage: int              # floor – nail/restaurant need 0 (ground)
    kueche: bool            # kitchen – required for restaurant
    lueftung: bool          # ventilation – required for nail (chemicals)
    wasseranschluss: bool   # water connections – required for nail
    starkstrom: bool        # 3-phase power – required for industrial kitchen
    parkplaetze: bool

    # Location
    stadt: str, bundesland: str, plz: str, adresse: str
    lat: Decimal, lng: Decimal  # geocoded coordinates

    # AI fields
    embedding: Vector(1536)     # pgvector – semantic search
    titel: str, beschreibung: str

    # Meta
    status: str             # active | inactive | deleted
    raw_data: JSONB         # full scraped payload – re-parse without re-crawl
    first_seen: DateTime
    last_seen: DateTime
```

### `location_intel` – location cache per PLZ

```python
class LocationIntel(Base):
    plz: str, radius_m: int     # composite key

    # Demographics (Destatis API)
    einwohner: int
    kaufkraft_index: Decimal    # 100 = DE average, Frankfurt ~115
    altersstruktur: JSONB       # {"0-18": 18, "18-65": 62, "65+": 20}

    # Competitors (Overpass API – cached forever)
    competitors: JSONB          # [{name, category, distance_m, rating}]
    competitor_count: int

    # Economics
    mietspiegel: Decimal        # avg €/m² in area
    leerstandsquote: Decimal    # vacancy rate

    # Previous tenant
    vormieter_typ: str          # "nail" | "restaurant" | "unknown"
    vormieter_data: JSONB
```

**Why separate from listings:** One PLZ can have hundreds of listings. Cache
location data once, reuse across all listings in same area.

### `listing_scores` – scoring results per business type

```python
class ListingScore(Base):
    listing_id: UUID, branche: str  # composite PK (one listing → multiple scores)

    # Score breakdown 0.0–10.0
    score_gesamt: Decimal
    score_location: Decimal
    score_financial: Decimal
    score_physical: Decimal
    score_market: Decimal

    # Revenue estimate
    revenue_min: Decimal
    revenue_max: Decimal
    revenue_confidence: Decimal  # 0.0–1.0

    explanation: JSONB  # {"strengths": [...], "weaknesses": [...]}
```

**Why separate from listings:** Scores can be recalculated when weights change
without touching raw listing data.

---

## Scoring Logic

### Nail Studio
```
score =
  w1 × wasseranschluss    (required – disqualify if missing)
  w2 × lueftung
  w3 × fussgaenger_traffic (from location_intel)
  w4 × normalize(mietpreis / flaeche_m2)
  w5 × parkplaetze
  - penalty if etage > 0
  - penalty if competitor_count > threshold
```

### Restaurant
```
score =
  w1 × kueche_vorhanden   (required – disqualify if missing)
  w2 × starkstrom
  w3 × normalize(sitzplaetze)
  w4 × 1 / competitor_density
  w5 × kaufkraft_index
  - penalty if ablöse_overpriced vs mietspiegel
```

### Revenue Estimation Benchmarks (Germany)
```
Nail Studio:  flaeche_m2 × €800–1,400/m²/year
              × (kaufkraft_index / 100)
              × (1 - competitor_density_factor)

Restaurant:   sitzplaetze × €2,000–4,500/seat/year
              × (kaufkraft_index / 100)
              × fussgaenger_factor
```

---

## Implemented Code Details

### `core/ports/crawler_port.py`

Key design: uses `CrawlOptions` dataclass instead of `**kwargs` for type safety.

```python
@dataclass
class CrawlOptions:
    extraction_schema: dict | None = None   # JSON schema for structured extraction
    css_selector: str | None = None
    wait_for: str | None = None
    js_code: str | list[str] | None = None
    timeout_ms: int = 30_000
    cache: bool = False

class CrawlerPort(ABC):
    @abstractmethod
    async def crawl(self, url: str, options: CrawlOptions | None = None) -> CrawlResult: ...

    async def crawl_many(self, urls: list[str], options: CrawlOptions | None = None,
                         max_concurrent: int = 3) -> list[CrawlResult]:
        # Default semaphore-based concurrency – adapters inherit for free
```

**Why `CrawlOptions` instead of `**kwargs`:**
- Autocomplete works in IDE
- Pylance catches typos at compile time
- Easy to extend without breaking signatures
- Adapters map to their own internal params

### `adapters/crawlers/crawl4ai_adapter.py`

Key issues fixed from Pylance errors:
- `CrawlerRunConfig` does not accept `None` – build kwargs dict conditionally
- `arun()` return type misidentified as `AsyncGenerator` – use `# type: ignore[union-attr]`
- `markdown_v2` deprecated – use `result.markdown.raw_markdown`

```python
# Pattern: only pass non-None values to CrawlerRunConfig
run_cfg_kwargs: dict = {"cache_mode": CacheMode.BYPASS}
if opts.extraction_schema is not None:
    run_cfg_kwargs["extraction_strategy"] = JsonCssExtractionStrategy(opts.extraction_schema)
run_cfg = CrawlerRunConfig(**run_cfg_kwargs)
```

---

## Data Sources

| Source | Usage | Cost |
|---|---|---|
| ImmobilienScout24 | Listings crawl | Free (scraping) |
| eBay Kleinanzeigen | Listings + Ablöse | Free (scraping) |
| OSM Overpass API | Competitor search in radius | Free |
| Nominatim (OSM) | Geocoding addresses | Free |
| Destatis API | Demographics per PLZ | Free |
| Mapbox GL JS | Map rendering | Free (50k loads/month) |
| Claude API | LLM extraction + agent | Pay per use |
| OpenAI | Embeddings only | Pay per use |

---

## Environment Variables

```env
ENV=development
LOG_LEVEL=debug

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/immo_ai
REDIS_URL=redis://localhost:6379

# Swap providers without code changes
CRAWLER_PROVIDER=crawl4ai        # crawl4ai | playwright | httpx
LLM_PROVIDER=anthropic           # anthropic | openai | ollama
MAP_PROVIDER=overpass            # overpass | google_maps
EMBEDDING_PROVIDER=openai        # openai | local

ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_MAPS_API_KEY=

CRAWL_HEADLESS=true
CRAWL_MAX_CONCURRENT=3
CRAWL_INTERVAL_HOURS=6
```

---

## Local Development

```bash
just up        # start Docker: postgres, redis, pgadmin, redisinsight
just migrate   # run alembic migrations
just dev       # start FastAPI on :8000
cd apps/web && npm run dev  # Next.js on :3000

# Services
pgAdmin     → http://localhost:5050  (admin@local.dev / admin)
RedisInsight → http://localhost:5540
FastAPI docs → http://localhost:8000/docs
```

Docker services defined in `docker-compose.yml`:
- `supabase/postgres:15.6.1.117` – includes pgvector + PostGIS
- `redis:7-alpine`
- `dpage/pgadmin4`
- `redis/redisinsight`

---

## Deployment Phases

### Phase 1 – Local (current)
Everything on localhost via Docker Compose.

### Phase 2 – Simple Hosting
```
Frontend  → Vercel (free)
Backend   → Railway (~$5/month)
Database  → Supabase (free tier, has pgvector built-in)
Redis     → Upstash (free: 10k req/day)
```
Migration = change DATABASE_URL + REDIS_URL in env. Zero code changes.

### Phase 3 – Google Cloud
```
FastAPI   → Cloud Run (scale to zero, 180k vCPU-sec/month free)
Workers   → Cloud Run Jobs (triggered by Cloud Scheduler)
Database  → Supabase or Cloud SQL
Redis     → Upstash or Cloud Memorystore
```

---

## What Still Needs to Be Built (Priority Order)

### Priority 1 – Core files (paste from outputs/core.zip)
- [ ] `core/config.py`
- [ ] `core/database.py`
- [ ] `core/models.py`
- [ ] `core/container.py`
- [ ] `core/ports/*.py`

### Priority 2 – Missing core utilities
- [ ] `core/redis.py` – Redis client singleton (same pattern as database.py)
- [ ] `core/logging.py` – structlog configuration
- [ ] `core/schemas.py` – Pydantic schemas for API (separate from ORM models)
- [ ] Delete `main.py` at project root (created by `uv init`, not needed)

### Priority 3 – Alembic setup
```bash
uv run alembic init alembic
# Edit alembic/env.py to use async engine from core.database
# Edit alembic.ini: sqlalchemy.url = (read from settings)
just migration "initial schema"
just migrate
```

### Priority 4 – LLM adapter
- [ ] `adapters/llm/anthropic_adapter.py`
  - Implement `LLMPort` Protocol
  - `complete()` → `anthropic.Anthropic().messages.create()`
  - `complete_structured()` → use instructor library or tool_use for Pydantic output

### Priority 5 – Map adapter
- [ ] `adapters/maps/overpass_adapter.py`
  - Query: `[out:json]; node["shop"="beauty"](around:500,{lat},{lng}); out;`
  - Categories: nail=`shop=beauty`, restaurant=`amenity=restaurant`
  - Geocoding via Nominatim (free OSM geocoder)

### Priority 6 – Embedding adapter
- [ ] `adapters/embeddings/openai_embedding.py`
  - `dimensions = 1536` for `text-embedding-3-small`
  - Batch `embed_many()` to reduce API calls

### Priority 7 – FastAPI skeleton
- [ ] `apps/api/main.py` – lifespan, CORS, router registration
- [ ] `apps/api/dependencies.py` – wire `get_db()`, `get_crawler()`, `get_llm()`
- [ ] `apps/api/routers/listings.py` – GET /listings with filters

### Priority 8 – Crawler services
- [ ] `services/crawler/immoscout_crawler.py`
  - Crawl search results page → extract listing URLs
  - Crawl each listing detail page with `CrawlOptions(extraction_schema=...)`
  - Upsert to `listings` table (update `last_seen` if exists)

### Priority 9 – Scoring engine
- [ ] `services/scoring/weights.py` – tunable weight constants
- [ ] `services/scoring/base_scorer.py` – abstract base with normalize helpers
- [ ] `services/scoring/nail_scorer.py`
- [ ] `services/scoring/restaurant_scorer.py`

### Priority 10 – Workers
- [ ] `workers/crawl_worker.py` – APScheduler trigger every 6h
- [ ] `workers/intel_worker.py` – enrich new listings with Overpass + Destatis

---

## Key Coding Conventions

**No `**kwargs` in interfaces** – always use typed dataclasses (`CrawlOptions`).

**ABC for ports with shared logic, Protocol for pure interfaces:**
```python
# CrawlerPort → ABC (crawl_many has default implementation)
# LLMPort, MapPort, EmbeddingPort → Protocol (structural subtyping)
```

**Adapters never import from each other** – only from `core/ports/`.

**`container.py` is the only place** that knows about concrete adapter classes.
Everything else uses ports.

**`@lru_cache` on factory functions** – adapters are singletons.

**`raw_data JSONB` always stored** – never lose scraped data even if parsing
logic changes later.

**Cache aggressively** – Overpass/Destatis results stored in `location_intel`
permanently. External APIs called once per PLZ only.

**`# type: ignore[union-attr]`** on crawl4ai result attributes – crawl4ai has
poor type stubs, this is expected and documented.

---

## Alembic Configuration Notes

When setting up alembic for async SQLAlchemy:

```python
# alembic/env.py – key parts
from core.database import Base
from core.models import Listing, LocationIntel, ListingScore  # noqa: F401

target_metadata = Base.metadata

# Must use run_async_migrations pattern for asyncpg
def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    # ... async context
```

---

## Common justfile Commands

```bash
just up                          # start Docker services
just down                        # stop Docker services
just dev                         # uvicorn apps.api.main:app --reload
just migrate                     # alembic upgrade head
just migration "description"     # alembic revision --autogenerate
just db-reset                    # drop volumes + recreate + migrate
just lint                        # ruff check + format
just test                        # pytest -v
just crawl                       # run crawl_worker manually
just playwright                  # install Chromium for Playwright
```
