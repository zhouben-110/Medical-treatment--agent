import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from medical_kb_mcp import db as mcp_db
from medical_kb_mcp.models import Disease


# 固定的 mock embedding 值（1024 维）
_EMB_A = [1.0] + [0.0] * 1023  # 普通感冒
_EMB_B = [0.9] + [0.1] + [0.0] * 1022  # 流行性感冒（与 A 相似）
_EMB_QUERY = [1.0] + [0.0] * 1023  # 查询用，与 A 完全相同


@pytest_asyncio.fixture
async def seeded(disease_sessionmaker):
    sm = disease_sessionmaker
    mcp_db.set_sessionmaker(sm)
    async with sm() as s:
        s.add_all([
            Disease(name="普通感冒", symptoms=["发热", "咳嗽", "流涕", "咽痛"],
                    symptom_embedding=_EMB_A,
                    description="上呼吸道感染", treatment="对症", when_to_see_doctor="高热不退", severity="轻"),
            Disease(name="流行性感冒", symptoms=["发热", "乏力", "肌肉酸痛", "咳嗽"],
                    symptom_embedding=_EMB_B,
                    description="流感病毒", treatment="奥司他韦", when_to_see_doctor="呼吸困难", severity="中"),
        ])
        await s.commit()
    yield sm
    mcp_db.set_sessionmaker(None)


@pytest.mark.asyncio
@patch("medical_kb_mcp.vectors.embed_query", new_callable=AsyncMock, return_value=_EMB_QUERY)
async def test_search_ranks_by_similarity(mock_embed, seeded):
    res = await mcp_db.search_diseases_by_symptoms(["发热", "咳嗽", "流涕", "咽痛"])
    assert len(res) >= 1
    assert res[0].name == "普通感冒"  # 与 query embedding 完全匹配
    assert res[0].match_score > 0.9


@pytest.mark.asyncio
async def test_search_empty_returns_empty(seeded):
    assert await mcp_db.search_diseases_by_symptoms([]) == []


@pytest.mark.asyncio
async def test_get_detail_exact_and_missing(seeded):
    d = await mcp_db.get_disease_detail("普通感冒")
    assert d is not None and d.treatment == "对症"
    assert await mcp_db.get_disease_detail("不存在的病") is None
