# immo-ai Usage Guide

## Prerequisites

- **Python 3.12+**
- **Docker** (for PostgreSQL + Redis)
- **uv** – Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **just** – Task runner ([install](https://just.systems/man/en/installation.html))
- **API keys** – At least one of: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`

---

## 1. Initial Setup

```bash
# Clone the repo
git clone <repo-url> && cd immo-ai

# Install Python dependencies
uv sync

# Copy environment template and fill in your keys
cp .env.example .env
```

Edit `.env` with your values:

```env
ENV=development
LOG_LEVEL=debug

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/immo_ai
REDIS_URL=redis://localhost:6379

# Adapter selection
CRAWLER_PROVIDER=crawl4ai
LLM_PROVIDER=anthropic
MAP_PROVIDER=overpass
EMBEDDING_PROVIDER=openai

# API Keys (at minimum, set one LLM + one embedding key)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Crawling
CRAWL_HEADLESS=true
CRAWL_MAX_CONCURRENT=3
CRAWL_INTERVAL_HOURS=6
```

> **Tip:** For local dev without API keys, set `LLM_PROVIDER=ollama` and
> `EMBEDDING_PROVIDER=local` to use free local alternatives.

---

## 2. Start Infrastructure

```bash
# Start PostgreSQL, Redis, pgAdmin, RedisInsight
just up

# Wait a few seconds for PostgreSQL to be ready, then run migrations
just migrate
```

**Service URLs after startup:**

| Service | URL | Credentials |
|---|---|---|
| PostgreSQL | `localhost:5432` | postgres / postgres |
| Redis | `localhost:6379` | – |
| pgAdmin | http://localhost:5050 | admin@local.dev / admin |
| RedisInsight | http://localhost:5540 | – |

---

## 3. Run the API Server

```bash
just dev
```

The FastAPI server starts at **http://localhost:8000**.

- Swagger docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

---

## 4. API Endpoints

### Listings

```bash
# List all active listings (paginated)
curl http://localhost:8000/api/listings

# Filter by city and price
curl "http://localhost:8000/api/listings?stadt=Berlin&max_mietpreis=2000"

# Filter by area
curl "http://localhost:8000/api/listings?min_flaeche=50&max_flaeche=200"

# Get a single listing
curl http://localhost:8000/api/listings/{listing_id}

# Create a listing manually
curl -X POST http://localhost:8000/api/listings \
  -H "Content-Type: application/json" \
  -d '{
    "source": "manual",
    "titel": "Gewerberaum Berlin Mitte",
    "stadt": "Berlin",
    "plz": "10115",
    "mietpreis": 1500,
    "flaeche_m2": 80,
    "etage": 0,
    "wasseranschluss": true,
    "lueftung": true
  }'

# Update a listing
curl -X PATCH http://localhost:8000/api/listings/{listing_id} \
  -H "Content-Type: application/json" \
  -d '{"mietpreis": 1600}'

# Soft-delete a listing
curl -X DELETE http://localhost:8000/api/listings/{listing_id}
```

### Scoring & Analysis

```bash
# Calculate score for a listing (nail studio or restaurant)
curl -X POST "http://localhost:8000/api/analysis/scores/{listing_id}/calculate?branche=nail"
curl -X POST "http://localhost:8000/api/analysis/scores/{listing_id}/calculate?branche=restaurant"

# Get existing scores
curl http://localhost:8000/api/analysis/scores/{listing_id}
curl "http://localhost:8000/api/analysis/scores/{listing_id}?branche=nail"

# Get location intelligence for a PLZ
curl http://localhost:8000/api/analysis/intel/10115
```

### AI Chat (Vietnamese)

```bash
# Stream a conversation with the AI agent (SSE)
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Tìm cho tôi tiệm nail ở Berlin giá dưới 2000 Euro"}
    ],
    "branche": "nail"
  }'
```

The response streams as Server-Sent Events (SSE):

```
data: {"type": "chunk", "content": "Tôi đã tìm thấy"}
data: {"type": "chunk", "content": " một số địa điểm"}
...
data: {"type": "done"}
```

---

## 5. Run Crawlers

### One-time manual crawl

```bash
just crawl
```

This crawls ImmobilienScout24 and Kleinanzeigen for 10 German cities (Berlin, Hamburg, München, Köln, Frankfurt, Stuttgart, Düsseldorf, Dortmund, Essen, Leipzig).

### Scheduled crawling (background worker)

```bash
# Starts APScheduler – runs once immediately, then every CRAWL_INTERVAL_HOURS
uv run python -m workers.crawl_worker
```

### Location intel enrichment

```bash
# Enriches new listings with competitor + demographics data
uv run python -m workers.intel_worker
```

---

## 6. Swap Providers

Change a single `.env` variable — zero code changes required.

### LLM Provider

```env
LLM_PROVIDER=anthropic    # Claude API (best for Vietnamese/German)
LLM_PROVIDER=openai       # GPT-4o
LLM_PROVIDER=ollama       # Free local (requires Ollama running)
```

### Crawler

```env
CRAWLER_PROVIDER=crawl4ai     # AI extraction + JS rendering
CRAWLER_PROVIDER=playwright   # Full browser (for heavy JS sites)
CRAWLER_PROVIDER=httpx        # Fast, static pages only
```

### Maps / Geocoding

```env
MAP_PROVIDER=overpass       # Free (OSM Overpass + Nominatim)
MAP_PROVIDER=google_maps    # Paid (requires GOOGLE_MAPS_API_KEY)
```

### Embeddings

```env
EMBEDDING_PROVIDER=openai   # OpenAI text-embedding-3-small (best quality)
EMBEDDING_PROVIDER=local    # Free hash-based (dev/testing only, no semantic search)
```

---

## 7. Database Management

```bash
# Create a new migration after changing models
just migration "add new column"

# Apply all pending migrations
just migrate

# Reset database completely (drops volumes!)
just db-reset

# Access pgAdmin UI
open http://localhost:5050
# Connect to: host=postgres, port=5432, user=postgres, password=postgres
```

---

## 8. Development Commands

```bash
just              # Show all available commands
just dev          # Start FastAPI dev server (hot reload)
just up           # Start Docker services
just down         # Stop Docker services
just logs         # Follow Docker logs
just lint         # Run ruff linter + formatter
just typecheck    # Run mypy type checker
just test         # Run pytest
just crawl        # Manual crawl run
just playwright   # Install Chromium for Playwright adapter
```

---

## 9. Using with Ollama (Free, No API Keys)

For fully local development without paying for API keys:

```bash
# 1. Install Ollama: https://ollama.com
# 2. Pull a model
ollama pull llama3

# 3. Set .env
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=local

# 4. Start normally
just up && just migrate && just dev
```

---

## 10. Scoring Explained

### Nail Studio Score (0–10)

| Factor | Weight | Notes |
|---|---|---|
| Wasseranschluss | 20% | **Required** – disqualifies if missing |
| Lüftung | 18% | Important for nail chemicals |
| Mietpreis/m² | 15% | Lower is better |
| Fußgänger traffic | 15% | From location intel |
| Parkplätze | 10% | Nice to have |
| Etage penalty | 10% | Ground floor preferred |
| Competitor penalty | 12% | Fewer nearby nail studios = better |

**Revenue estimate:** `flaeche_m2 × €800–1,400/m²/year × kaufkraft_factor`

### Restaurant Score (0–10)

| Factor | Weight | Notes |
|---|---|---|
| Küche | 22% | **Required** – disqualifies if missing |
| Fläche | 15% | Larger = more seats = more revenue |
| Kaufkraft | 15% | Higher purchasing power = better |
| Competitor density | 15% | Fewer nearby restaurants = better |
| Starkstrom | 12% | 3-phase power for industrial kitchen |
| Ablöse vs Mietspiegel | 10% | Penalty if overpriced |
| Etage penalty | 11% | Ground floor preferred |

**Revenue estimate:** `seats × €2,000–4,500/seat/year × kaufkraft_factor`

---

## Troubleshooting

### Docker services won't start

```bash
# Check if ports are already in use
lsof -i :5432   # PostgreSQL
lsof -i :6379   # Redis

# Restart from scratch
just down && just up
```

### Migration fails

```bash
# Check if PostgreSQL is ready
docker compose exec postgres pg_isready -U postgres

# Full reset if needed
just db-reset
```

### Crawl4AI issues

```bash
# Install browser for Playwright fallback
just playwright

# Switch to Playwright adapter
# In .env: CRAWLER_PROVIDER=playwright
```

### Import errors

```bash
# Reinstall dependencies
uv sync --reinstall
```
