from typing import Optional
import redis.asyncio as aioredis
from app.core.config import REDIS_URL

_client: Optional[aioredis.Redis] = None


async def init_redis():
    global _client
    _client = aioredis.from_url(REDIS_URL, decode_responses=True)


async def close_redis():
    if _client:
        await _client.aclose()


def get_redis() -> aioredis.Redis:
    if _client is None:
        raise RuntimeError("Redis not initialized")
    return _client
