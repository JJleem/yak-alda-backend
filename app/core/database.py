from typing import Optional
import asyncpg
from app.core.config import DATABASE_URL

_pool: Optional[asyncpg.Pool] = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL)


async def close_db():
    if _pool:
        await _pool.close()


def get_db() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB not initialized")
    return _pool
