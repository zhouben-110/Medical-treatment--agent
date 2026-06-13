import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select, func
from medical_kb_mcp import seed_diseases
from medical_kb_mcp.models import Disease

# mock embedding: 25 个固定向量
_MOCK_EMBEDDINGS = [[float(i)] + [0.0] * 1023 for i in range(25)]


@pytest.mark.asyncio
@patch("medical_kb_mcp.vectors.embed_texts", new_callable=AsyncMock, return_value=_MOCK_EMBEDDINGS)
@patch("medical_kb_mcp.seed_diseases.ensure_embedding_column", new_callable=AsyncMock)
async def test_seed_is_idempotent(mock_migrate, mock_embed, disease_sessionmaker):
    sm = disease_sessionmaker
    first = await seed_diseases.seed(sm)
    assert first == 25
    second = await seed_diseases.seed(sm)   # re-run inserts nothing
    assert second == 0
    async with sm() as s:
        total = (await s.execute(select(func.count()).select_from(Disease))).scalar_one()
    assert total == 25


@pytest.mark.asyncio
@patch("medical_kb_mcp.vectors.embed_texts", new_callable=AsyncMock, return_value=_MOCK_EMBEDDINGS)
@patch("medical_kb_mcp.seed_diseases.ensure_embedding_column", new_callable=AsyncMock)
async def test_seed_backfills_embeddings(mock_migrate, mock_embed, disease_sessionmaker):
    """已有疾病但缺少 embedding 时，seed 应补算。"""
    sm = disease_sessionmaker
    # 先插入一个没有 embedding 的疾病
    async with sm() as s:
        s.add(Disease(name="普通感冒", symptoms=["发热", "咳嗽"], description="test", severity="轻"))
        await s.commit()

    await seed_diseases.seed(sm)

    async with sm() as s:
        d = (await s.execute(select(Disease).where(Disease.name == "普通感冒"))).scalars().first()
        assert d is not None
        assert d.symptom_embedding is not None  # embedding 已补算
