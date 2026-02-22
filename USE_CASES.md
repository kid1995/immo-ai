# Use Cases & Technology Map

## Overview

immo-ai has two core use cases that are **tightly coupled** — UC1 is the data
producer that runs continuously in the background, while UC2 is the consumer
that answers user queries in real time. UC2 is only as good as the data UC1 has
collected.

```
UC1 (Crawler Pipeline)  ──feeds──►  PostgreSQL  ◄──reads──  UC2 (AI Search)
```

---

## UC1 – Market Intelligence Pipeline

A scheduled background pipeline that continuously crawls German commercial real
estate platforms, enriches each listing with location intelligence, scores it
per business type, and stores everything in the database.

**Trigger:** APScheduler every 6 hours (Phase 1–2) → Cloud Scheduler (Phase 3)

**Actor:** No human interaction required. Runs autonomously.

```mermaid
flowchart TD
    A([APScheduler / Cloud Scheduler]) --> B

    subgraph Crawler Service
        B[immoscout_crawler.py<br/>kleinanzeigen_crawler.py]
    end

    subgraph Crawl4AI Adapter
        B -->|URL list| C[crawl4ai_adapter.py<br/>Playwright headless browser]
        C -->|html · markdown · structured_data| D
    end

    subgraph LLM Adapter
        D[anthropic_adapter.py] -->|extract fields from markdown| E
        E[ListingData<br/>mietpreis · flaeche · stadt]
    end

    subgraph Embedding Adapter
        E -->|beschreibung text| F[openai_embedding.py]
        F -->|vector 1536 dims| G
    end

    subgraph DB writes
        G[(listings<br/>embedding VECTOR<br/>raw_data JSONB)]
    end

    G -->|new listing id| H

    subgraph Intel Service
        H[competitors.py] -->|lat · lng · radius 500m| I
        I[overpass_adapter.py<br/>OpenStreetMap free API]
        I -->|list of Competitor| J[demographics.py<br/>Destatis API]
        J -->|kaufkraft · einwohner| K
    end

    subgraph DB writes
        K[(location_intel<br/>per PLZ · cached forever)]
    end

    K --> L

    subgraph Scoring Engine
        L[base_scorer.py]
        L --> M[nail_scorer.py]
        L --> N[restaurant_scorer.py]
        M & N -->|weights.py| O
        O[score_gesamt · score_location<br/>revenue_min · revenue_max]
    end

    subgraph DB writes
        O --> P[(listing_scores<br/>per listing + branche)]
    end

    P --> Q([Dashboard ready for UC2])

    style A fill:#f5a623,color:#000
    style Q fill:#7ed321,color:#000
```

---

## UC2 – AI Search Assistant

A real-time query flow triggered by a user typing in Vietnamese. The AI agent
parses intent, calls internal tools backed by the database UC1 has populated,
and returns a ranked, explained result in Vietnamese.

**Trigger:** User submits a query in the Next.js chat interface.

**Actor:** End user (Vietnamese business owner in Germany).

```mermaid
flowchart TD
    A([User types in Vietnamese<br/>'Tìm tiệm nail Frankfurt<br/>giá dưới 1500€ tầng trệt']) --> B

    subgraph Next.js 15
        B[Vercel AI SDK<br/>streaming chat UI]
    end

    B -->|POST /api/agent SSE stream| C

    subgraph FastAPI
        C[routers/agent.py]
    end

    C --> D

    subgraph AI Agent Service
        D[agent.py<br/>LangChain orchestrator]
        D -->|parse intent + extract filters| E[anthropic_adapter.py<br/>Claude API]
        E -->|branche · stadt · mietpreis_max · etage| F

        subgraph Tools
            F[tools.py]
            F --> G[search_listings<br/>SQL filter query]
            F --> H[semantic_search<br/>pgvector cosine distance]
            F --> I[get_scores<br/>fetch listing_scores]
            F --> J[get_competitors<br/>fetch location_intel]
        end
    end

    subgraph Embedding Adapter
        H -->|embed query text first| N[openai_embedding.py]
        N -->|query vector 1536 dims| H
    end

    subgraph DB reads
        G -->|WHERE mietpreis < 1500<br/>AND stadt = Frankfurt| K[(listings)]
        H -->|embedding <=> query_vector| K
        I --> L[(listing_scores)]
        J --> M[(location_intel)]
    end

    K & L & M -->|raw results| O

    subgraph AI Agent Service
        O[agent.py<br/>synthesize results]
        O -->|ranked listings + context| P[anthropic_adapter.py<br/>generate Vietnamese explanation]
    end

    P -->|streaming response| B
    B --> Q([User sees ranked results<br/>with Vietnamese explanation<br/>+ map pins])

    style A fill:#f5a623,color:#000
    style Q fill:#7ed321,color:#000
```

---

## Relationship Between UC1 and UC2

UC1 and UC2 share the same database and adapter layer. They never call each
other directly — PostgreSQL is the contract between them.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Shared Layer                                │
│                                                                     │
│   adapters/llm/anthropic_adapter.py   ← used by BOTH UC1 and UC2   │
│   adapters/embeddings/openai_embedding.py  ← used by BOTH          │
│   adapters/maps/overpass_adapter.py   ← UC1 only                   │
│   adapters/crawlers/crawl4ai_adapter.py  ← UC1 only                │
│                                                                     │
│   PostgreSQL                                                        │
│   ├── listings          ← UC1 writes  │  UC2 reads                 │
│   ├── location_intel    ← UC1 writes  │  UC2 reads                 │
│   └── listing_scores    ← UC1 writes  │  UC2 reads                 │
└─────────────────────────────────────────────────────────────────────┘
```

| Dimension | UC1 | UC2 |
|---|---|---|
| Trigger | Time-based (every 6h) | User-based (on demand) |
| Direction | Writes to DB | Reads from DB |
| Latency | Minutes per run | Seconds per query |
| LLM usage | Extract structured data from HTML | Generate Vietnamese answers |
| Embedding | Embed listing descriptions | Embed user query |
| Maps | Fetch competitor data | Display results on map |
| Dependency | Independent | Depends on UC1 having run |

**Quality relationship:** UC2 answer quality improves directly with UC1 data
quality. A freshly initialized database with no listings returns no results. A
database with 3 months of crawled and scored listings returns highly relevant,
ranked, explained results.

---

## Technology Map

| Technology | UC1 | UC2 | Why |
|---|---|---|---|
| **Crawl4AI** | ✅ crawl listings | — | AI-assisted HTML extraction, no manual parser |
| **Playwright** | ✅ fallback browser | — | JS-rendered pages, login sessions |
| **httpx** | ✅ simple requests | — | Static pages, faster than browser |
| **APScheduler** | ✅ trigger every 6h | — | Run pipeline without user |
| **LangChain** | — | ✅ agent orchestration | Tool calling, multi-step reasoning |
| **Claude API** | ✅ extract fields from markdown | ✅ answer in Vietnamese | Best multilingual understanding |
| **OpenAI Embeddings** | ✅ embed descriptions | ✅ embed user query | Same model → compatible vectors |
| **pgvector** | ✅ store vectors | ✅ cosine search | One DB for everything |
| **PostGIS** | ✅ store coordinates | ✅ map display | Geo queries in SQL |
| **Overpass API** | ✅ fetch competitors | — | Free, OSM-based, accurate in DE |
| **Destatis API** | ✅ demographics per PLZ | — | Official DE statistics, free |
| **Redis** | ✅ job queue (arq) | ✅ cache hot queries | Avoid repeat API calls |
| **FastAPI** | — | ✅ REST + SSE endpoints | Async, auto docs |
| **Next.js 15** | — | ✅ chat UI + map | SSE streaming, Server Components |
| **Mapbox GL JS** | — | ✅ map rendering | Free 50k loads/month, customizable |
| **Vercel AI SDK** | — | ✅ streaming chat | Native SSE, works with any LLM |
