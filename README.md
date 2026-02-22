# immo-ai

> AI-powered commercial real estate finder for Vietnamese business owners in Germany.
> Helps find nail studios, restaurant, and retail spaces by analyzing rent price, Ablöse, location intelligence, competitor density, and estimated revenue.

---

## Problem Statement

Vietnamese business owners in Germany (nail studios, restaurants, Imbiss) struggle to find suitable commercial spaces because:
- Listings are scattered across multiple German platforms (ImmobilienScout24, Kleinanzeigen, Immonet)
- Key data (Ablöse fairness, competitor density, foot traffic) is not aggregated anywhere
- Language and domain knowledge barriers make evaluation difficult

**immo-ai** solves this by automatically crawling listings, enriching them with location intelligence, scoring them per business type, and providing an AI chat assistant in Vietnamese.

---

## Core Features

### Phase 1 – Local Development
- Automated crawling of ImmobilienScout24 and eBay Kleinanzeigen
- Filter listings by: rent price, Ablöse, area (m²), city, floor, features
- Business-type scoring engine (nail studio vs. restaurant)
- Basic map view with listing pins

### Phase 2 – Simple Hosting
- User accounts and saved searches
- Real-time alerts when new matching listings appear
- Competitor analysis via OpenStreetMap Overpass API (free)
- Location intelligence: demographics, Kaufkraft index per PLZ

### Phase 3 – Google Cloud
- Revenue estimation model per listing
- Full AI agent chat in Vietnamese (Claude API)
- Scheduled crawling via Cloud Scheduler + Cloud Run Jobs
- Advanced analytics: price trends by Bundesland, seasonality

---

## Input Parameters

| Category | Parameter | Description |
|---|---|---|
| Financial | `mietpreis` | Monthly rent (€/month) |
| | `ablöse` | Takeover fee |
| | `kaution` | Deposit (usually 3 months rent) |
| | `nebenkosten` | Utility costs |
| Physical | `flaeche_m2` | Area in m² |
| | `etage` | Floor (ground floor preferred) |
| | `kueche` | Kitchen available |
| | `lueftung` | Ventilation system |
| | `wasseranschluss` | Water connections |
| | `starkstrom` | 3-phase power |
| Location | `stadt` / `bundesland` | City / State |
| | `plz` | Postal code |
| | `fussgaengerzone` | Pedestrian zone proximity |
| | `parkplaetze` | Parking available |
| Business | `branche` | nail_studio / restaurant / imbiss |
| | `sitzplaetze` | Seating capacity (restaurant) |
| | `arbeitsplaetze` | Workstations (nail studio) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js 15 (Frontend)                   │
│  - Listing search & filters                                  │
│  - Map view (Mapbox GL JS)                                   │
│  - AI chat assistant (Vercel AI SDK streaming)               │
│  - Scoring dashboard                                         │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST / SSE
┌─────────────────────────────▼───────────────────────────────┐
│                    FastAPI (Python 3.12)                     │
│                                                             │
│  routers/listings.py   – search, filter, CRUD               │
│  routers/analysis.py   – scoring, intel per listing         │
│  routers/agent.py      – AI chat endpoint                   │
└──────┬──────────────┬───────────────┬────────────┬──────────┘
       │              │               │            │
┌──────▼───┐  ┌───────▼──────┐ ┌─────▼─────┐ ┌───▼──────────┐
│ Listing  │  │   Crawler    │ │   Intel   │ │  AI Agent    │
│ Service  │  │   Service    │ │  Service  │ │  Service     │
│          │  │              │ │           │ │              │
│ search   │  │ Immoscout    │ │ Demografie│ │ LangChain    │
│ filter   │  │ Kleinanzeige │ │ Competitors│ │ Claude API   │
│ scoring  │  │ Immonet      │ │ Economics │ │ Tool calling │
└──────────┘  └──────────────┘ └───────────┘ └──────────────┘
                              │
              ┌───────────────▼───────────────┐
              │  PostgreSQL + pgvector + PostGIS│
              │  Redis (cache + job queue)      │
              └───────────────────────────────┘
```

### Adapter Pattern (Ports & Adapters)

All external technology dependencies are abstracted behind interfaces. Swap providers by changing a single `.env` variable — no code changes required.

```
core/ports/          ← Interfaces (CrawlerPort, LLMPort, MapPort, EmbeddingPort)
adapters/crawlers/   ← crawl4ai_adapter, playwright_adapter, httpx_adapter
adapters/llm/        ← anthropic_adapter, openai_adapter, ollama_adapter
adapters/maps/       ← overpass_adapter, google_maps_adapter
adapters/embeddings/ ← openai_embedding, local_embedding
```

**Switch example:**
```bash
# Use Claude
LLM_PROVIDER=anthropic

# Switch to OpenAI – zero code changes
LLM_PROVIDER=openai

# Switch crawler when Crawl4AI has issues
CRAWLER_PROVIDER=playwright
```

---

## Project Structure

```
immo-ai/
├── apps/
│   ├── api/                    # FastAPI gateway
│   │   ├── main.py
│   │   ├── dependencies.py     # Dependency injection (get_crawler, get_llm)
│   │   └── routers/
│   │       ├── listings.py
│   │       ├── analysis.py
│   │       └── agent.py
│   └── web/                    # Next.js 15
│
├── core/
│   ├── config.py               # pydantic-settings, reads .env
│   ├── database.py             # SQLAlchemy async engine
│   ├── models.py               # ORM models
│   ├── di_container.py            # Adapter factory / DI container
│   └── ports/                  # Abstract interfaces
│       ├── crawler_port.py
│       ├── llm_port.py
│       ├── map_port.py
│       └── embedding_port.py
│
├── adapters/                   # Concrete implementations
│   ├── crawlers/
│   ├── llm/
│   ├── maps/
│   └── embeddings/
│
├── services/
│   ├── crawler/                # Site-specific scrapers
│   │   ├── immoscout_crawler.py
│   │   └── kleinanzeigen_crawler.py
│   ├── intel/                  # Location intelligence
│   │   ├── demographics.py     # Population density, age, Kaufkraft
│   │   ├── competitors.py      # Nearby businesses via Overpass API
│   │   └── revenue_estimator.py
│   ├── scoring/                # Business-type scoring engine
│   │   ├── base_scorer.py
│   │   ├── nail_scorer.py
│   │   ├── restaurant_scorer.py
│   │   └── weights.py          # Tunable score weights
│   └── agent/
│       ├── tools.py            # LangChain tools
│       └── agent.py            # AI agent orchestration
│
├── workers/
│   ├── crawl_worker.py         # Scheduled crawl jobs
│   └── intel_worker.py        # Location enrichment jobs
│
└── infra/
    └── init.sql                # PostgreSQL extensions
```

---

## Database Schema

```sql
-- Core listing
listings (
  id UUID, source, source_url,
  mietpreis, ablöse, kaution, nebenkosten,
  flaeche_m2, etage,
  stadt, bundesland, plz, adresse,
  koordinaten GEOGRAPHY(POINT, 4326),     -- PostGIS
  kueche, lueftung, parkplaetze, wasseranschluss, starkstrom,
  titel, beschreibung,
  embedding VECTOR(1536),                 -- pgvector semantic search
  raw_data JSONB,
  status, first_seen, last_seen
)

-- Location intelligence (enriched separately, reused across listings)
location_intel (
  koordinaten, radius_m,
  einwohner, kaufkraft_index, altersstruktur JSONB,
  competitors JSONB, competitor_count,
  mietspiegel, leerstandsquote,
  vormieter_typ, vormieter_data JSONB,
  updated_at
)

-- Scoring results per business type
listing_scores (
  listing_id, branche,
  score_gesamt, score_location, score_financial,
  score_physical, score_market,
  revenue_min, revenue_max, revenue_confidence,
  explanation JSONB,
  calculated_at
)
```

---

## Scoring Logic

### Nail Studio
```
score =
  w1 × wasseranschluss (required)
  w2 × lueftung_quality
  w3 × fussgaenger_traffic (normalized)
  w4 × normalize(mietpreis / flaeche_m2)
  w5 × parkplaetze
  - penalty × (etage > 0)
  - penalty × competitor_density_high
```

### Restaurant
```
score =
  w1 × kueche_vorhanden (required)
  w2 × normalize(sitzplaetze)
  w3 × starkstrom
  w4 × 1 / competitor_density
  w5 × kaufkraft_index
  - penalty × ablöse_overpriced
```

---

## Revenue Estimation Model

```
Nail Studio:
  base = flaeche_m2 × €800–1,400 (Umsatz/m²/Jahr benchmark DE)
  adjust × kaufkraft_index / 100
  adjust × (1 - competitor_density_factor)

Restaurant:
  base = sitzplaetze × €2,000–4,500 (Umsatz/Sitzplatz/Jahr benchmark DE)
  adjust × kaufkraft_index / 100
  adjust × fussgangerfrequenz_factor
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
| Mapbox GL JS | Map rendering (frontend) | Free (50k loads/month) |
| Claude API | AI agent + chat | Pay per use |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, Mapbox GL JS, Vercel AI SDK, shadcn/ui |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2.x async |
| Crawling | Crawl4AI, Playwright (fallback), httpx |
| AI / LLM | LangChain, Claude API (anthropic), OpenAI (fallback) |
| Database | PostgreSQL + pgvector + PostGIS |
| Cache / Queue | Redis, arq |
| Scheduling | APScheduler 3.x |
| Package manager | uv |
| Task runner | just |

---

## Deployment Phases

### Phase 1 – Local Development

**Goal:** Build and test the full stack locally.

```
Services (Docker):
  PostgreSQL + pgvector + PostGIS  → localhost:5432
  Redis                            → localhost:6379
  pgAdmin                          → localhost:5050
  RedisInsight                     → localhost:5540

App:
  FastAPI   → localhost:8000
  Next.js   → localhost:3000
```

**Quick start:**
```bash
just up        # start Docker services
just dev       # start FastAPI
cd apps/web && npm run dev  # start Next.js
```

**Environment:**
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/immo_ai
REDIS_URL=redis://localhost:6379
LLM_PROVIDER=anthropic
CRAWLER_PROVIDER=crawl4ai
MAP_PROVIDER=overpass
```

---

### Phase 2 – Simple Hosting (Railway + Supabase + Vercel)

**Goal:** Production-ready, low-cost, minimal DevOps.

```
Frontend  → Vercel (free hobby plan)
Backend   → Railway ($5/month, Docker deploy)
Database  → Supabase (free tier: PostgreSQL + pgvector + Auth)
Redis     → Upstash (free: 10k requests/day)
```

**Migration steps:**
1. Push Docker image to Railway (connect GitHub repo → auto deploy)
2. Create Supabase project → copy `DATABASE_URL`
3. Create Upstash Redis → copy `REDIS_URL`
4. Update environment variables → no code changes needed
5. Deploy Next.js to Vercel → connect GitHub repo

**Estimated cost: ~$5–10/month** (mostly Railway; Claude API pay-per-use)

---

### Phase 3 – Google Cloud

**Goal:** Scalable, production-grade, full observability.

```
Frontend       → Vercel (unchanged)
FastAPI API    → Cloud Run (scale to zero, free tier covers dev usage)
Crawl workers  → Cloud Run Jobs (triggered by Cloud Scheduler)
Database       → Supabase or Cloud SQL (PostgreSQL)
Redis          → Upstash or Cloud Memorystore
Maps/Places    → Google Maps Platform (competitor search with higher accuracy)
Monitoring     → Cloud Logging + Cloud Monitoring
```

**Why Google Cloud at this stage:**
- Cloud Run free tier: 180k vCPU-seconds/month (crawler jobs stay free)
- Cloud Scheduler: trigger crawl jobs every 6 hours (3 jobs free)
- Google Places API: superior POI data for competitor analysis in Germany
- Scale-to-zero: no idle cost during low traffic

**Migration steps:**
1. Containerize FastAPI → `Dockerfile` (already Docker-compatible from Phase 1)
2. Push to Google Artifact Registry
3. Deploy to Cloud Run: `gcloud run deploy`
4. Set up Cloud Scheduler → HTTP trigger → Cloud Run Job URL
5. Configure Secret Manager for API keys
6. Update `DATABASE_URL`, `REDIS_URL` in Cloud Run env vars

**Estimated cost after free tier: ~$5–15/month**

---

## Environment Variables Reference

```env
# App
ENV=development                  # development | production
LOG_LEVEL=debug

# Database
DATABASE_URL=postgresql+asyncpg://...

# Redis
REDIS_URL=redis://...

# Adapter selection (swap without code changes)
CRAWLER_PROVIDER=crawl4ai        # crawl4ai | playwright | httpx
LLM_PROVIDER=anthropic           # anthropic | openai | ollama
MAP_PROVIDER=overpass            # overpass | google_maps
EMBEDDING_PROVIDER=openai        # openai | local

# API Keys
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_MAPS_API_KEY=

# Crawling
CRAWL_HEADLESS=true
CRAWL_MAX_CONCURRENT=3
CRAWL_INTERVAL_HOURS=6
```

---

## Development Roadmap

| Phase | Week | Milestone |
|---|---|---|
| 1 | 1–2 | Crawl4AI scraper for ImmobilienScout24 + Kleinanzeigen |
| 1 | 3–4 | FastAPI CRUD + PostgreSQL schema + Alembic migrations |
| 1 | 5–6 | Next.js listing search UI + Mapbox map view |
| 2 | 7–8 | Scoring engine (nail + restaurant) |
| 2 | 9–10 | Overpass competitor analysis + demographics intel |
| 2 | 11–12 | User auth + saved searches + email alerts |
| 2 | 13–14 | Deploy Phase 2 (Railway + Supabase + Vercel) |
| 3 | 15–16 | Revenue estimation model |
| 3 | 17–18 | AI agent chat in Vietnamese (LangChain + Claude) |
| 3 | 19–20 | Migrate to Google Cloud Run + Cloud Scheduler |

---

## Key Design Decisions

**Ports & Adapters pattern** – All external integrations (LLM, crawler, maps) are abstracted. Switch providers via `.env`, never touch business logic.

**`location_intel` table is separate** – Location data is enriched independently and reused across all listings in the same area. One Overpass API call serves hundreds of listings.

**`listing_scores` table is separate** – Scores can be recalculated when weights change or new intel data arrives, without affecting raw listing data.

**`raw_data JSONB` column** – Always store the full scraped payload. If parsing logic changes, re-parse from raw data without re-crawling.

**Cache aggressively** – Competitor searches (Overpass), demographics (Destatis), and geocoding results are stored in `location_intel` permanently. External APIs are called only once per location.