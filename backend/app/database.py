import sys
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

if "pytest" in sys.modules:
    # Use NullPool in tests to prevent cross-event-loop connection reuse issues with asyncpg
    engine = create_async_engine(
        settings.database_url,
        echo=settings.sql_echo,
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.sql_echo,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=10,
        max_overflow=20,
    )
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # PostgreSQL 生产环境下尝试自动创建 HNSW 向量索引进行加速
        if "postgresql" in settings.database_url and "pytest" not in sys.modules:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_diseases_symptom_embedding "
                    "ON diseases USING hnsw (symptom_embedding vector_cosine_ops);"
                ))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not create pgvector HNSW index: {e}")
