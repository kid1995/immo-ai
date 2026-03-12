"""
Adapter factory – the only place that knows about concrete implementations.
All other modules import from core.ports, never from adapters directly.
"""

from functools import lru_cache

from core.config import settings
from core.ports import CrawlerPort, EmbeddingPort, LLMPort, MapPort


@lru_cache
def get_crawler() -> CrawlerPort:
    match settings.crawler_provider:
        case "crawl4ai":
            from adapters.crawlers.crawl4ai_adapter import Crawl4AIAdapter

            return Crawl4AIAdapter(headless=settings.crawl_headless)
        case "playwright":
            from adapters.crawlers.playwright_adapter import PlaywrightAdapter

            return PlaywrightAdapter(headless=settings.crawl_headless)
        case "httpx":
            from adapters.crawlers.httpx_adapter import HttpxAdapter

            return HttpxAdapter()
        case _:
            raise ValueError(f"Unknown crawler provider: {settings.crawler_provider}")


@lru_cache
def get_llm() -> LLMPort:
    match settings.llm_provider:
        case "anthropic":
            from adapters.llm.anthropic_adapter import AnthropicAdapter

            return AnthropicAdapter(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            )
        case "openai":
            from adapters.llm.openai_adapter import OpenAIAdapter

            return OpenAIAdapter(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        case "ollama":
            from adapters.llm.ollama_adapter import OllamaAdapter

            return OllamaAdapter()
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


@lru_cache
def get_map() -> MapPort:
    match settings.map_provider:
        case "overpass":
            from adapters.maps.overpass_adapter import OverpassAdapter

            return OverpassAdapter()
        case "google_maps":
            from adapters.maps.google_maps_adapter import GoogleMapsAdapter

            return GoogleMapsAdapter(api_key=settings.google_maps_api_key)
        case _:
            raise ValueError(f"Unknown map provider: {settings.map_provider}")


@lru_cache
def get_embedding() -> EmbeddingPort:
    match settings.embedding_provider:
        case "openai":
            from adapters.embeddings.openai_embedding import OpenAIEmbedding

            return OpenAIEmbedding(
                api_key=settings.openai_api_key,
                model=settings.openai_embedding_model,
                dimensions=settings.embedding_dimensions,
            )
        case "local":
            from adapters.embeddings.local_embedding import LocalEmbedding

            return LocalEmbedding()
        case _:
            raise ValueError(
                f"Unknown embedding provider: {settings.embedding_provider}"
            )
