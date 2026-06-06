import pytest
import pytest_asyncio
from medical_kb_mcp import db as mcp_db
from medical_kb_mcp.models import Disease


@pytest_asyncio.fixture
async def seeded(disease_sessionmaker):
    sm = disease_sessionmaker
    mcp_db.set_sessionmaker(sm)
    async with sm() as s:
        s.add_all([
            Disease(name="普通感冒", symptoms=["发热", "咳嗽", "流涕", "咽痛"],
                    description="上呼吸道感染", treatment="对症", when_to_see_doctor="高热不退", severity="轻"),
            Disease(name="流行性感冒", symptoms=["发热", "乏力", "肌肉酸痛", "咳嗽"],
                    description="流感病毒", treatment="奥司他韦", when_to_see_doctor="呼吸困难", severity="中"),
        ])
        await s.commit()
    yield sm
    mcp_db.set_sessionmaker(None)


@pytest.mark.asyncio
async def test_search_ranks_by_dice(seeded):
    res = await mcp_db.search_diseases_by_symptoms(["发热", "咳嗽", "流涕", "咽痛"])
    assert res[0].name == "普通感冒"          # exact 4/4 overlap wins
    assert res[0].match_score == 1.0
    assert set(res[0].matched_symptoms) == {"发热", "咳嗽", "流涕", "咽痛"}


@pytest.mark.asyncio
async def test_search_empty_returns_empty(seeded):
    assert await mcp_db.search_diseases_by_symptoms([]) == []


@pytest.mark.asyncio
async def test_get_detail_exact_and_missing(seeded):
    d = await mcp_db.get_disease_detail("普通感冒")
    assert d is not None and d.treatment == "对症"
    assert await mcp_db.get_disease_detail("不存在的病") is None
