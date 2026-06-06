import pytest
from sqlalchemy import select, func
from medical_kb_mcp import seed_diseases
from medical_kb_mcp.models import Disease


@pytest.mark.asyncio
async def test_seed_is_idempotent(disease_sessionmaker):
    sm = disease_sessionmaker
    first = await seed_diseases.seed(sm)
    assert first == 25
    second = await seed_diseases.seed(sm)   # re-run inserts nothing
    assert second == 0
    async with sm() as s:
        total = (await s.execute(select(func.count()).select_from(Disease))).scalar_one()
    assert total == 25
