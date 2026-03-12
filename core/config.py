from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ───────────────────────────────────
    env: str = "development"
    log_level: str = "debug"

    # ── Database ──────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/immo_ai"

    # ── Redis ─────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── Adapter selection ─────────────────────
    crawler_provider: str = "crawl4ai"  # crawl4ai | playwright | httpx
    llm_provider: str = "anthropic"  # anthropic | openai | ollama
    map_provider: str = "overpass"  # overpass | google_maps
    embedding_provider: str = "openai"  # openai | local

    # ── API Keys ──────────────────────────────
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_maps_api_key: str = ""

    # ── LLM Models ────────────────────────────
    anthropic_model: str = "claude-sonnet-4-5"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # ── Crawling ──────────────────────────────
    crawl_headless: bool = True
    crawl_max_concurrent: int = 3
    crawl_interval_hours: int = 6

    @property
    def is_production(self) -> bool:
        return self.env == "production"


# Singleton – import this everywhere
settings = Settings()
