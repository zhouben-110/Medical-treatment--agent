import pytest_asyncio
import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from medical_kb_mcp.config import get_mcp_settings
from medical_kb_mcp.models import Base


async def _ensure_test_db() -> str:
    """Create the *_test database if missing; return its async SQLAlchemy URL."""
    url = get_mcp_settings().database_url            # postgresql+asyncpg://.../medical_agent
    base, name = url.rsplit("/", 1)
    test_name = name + "_test"
    maint_dsn = base.replace("+asyncpg", "") + "/postgres"
    conn = await asyncpg.connect(dsn=maint_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", test_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{test_name}"')
    finally:
        await conn.close()
    return f"{base}/{test_name}"


@pytest_asyncio.fixture
async def disease_sessionmaker():
    """Async sessionmaker bound to an isolated test DB with a fresh diseases table."""
    test_url = await _ensure_test_db()
    engine = create_async_engine(test_url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    await engine.dispose()
