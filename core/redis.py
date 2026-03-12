"""Redis client singleton – same pattern as database.py."""

from functools import lru_cache

import redis.asyncio as redis

from core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    """Return a cached async Redis client."""
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )


async def close_redis() -> None:
    """Close the Redis connection pool. Call during app shutdown."""
    client = get_redis_client()
    await client.aclose()
