"""Request-level dependency injection for FastAPI routes."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.di_container import get_crawler, get_embedding, get_llm, get_map
from core.ports import CrawlerPort, EmbeddingPort, LLMPort, MapPort


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async database session – auto-commits on success, rollbacks on error."""
    async for session in get_db():
        yield session


def crawler(db: AsyncSession = Depends(db_session)) -> CrawlerPort:  # noqa: ARG001
    return get_crawler()


def llm() -> LLMPort:
    return get_llm()


def map_service() -> MapPort:
    return get_map()


def embedding() -> EmbeddingPort:
    return get_embedding()
