import pytest
from unittest.mock import MagicMock
from langchain_core.documents import Document

from medical_kb_mcp import vectors


@pytest.mark.asyncio
async def test_search_guidelines_maps_chunks(monkeypatch):
    fake_store = MagicMock()
    fake_store.similarity_search_with_score.return_value = [
        (Document(page_content="感冒应多休息多饮水"), 0.12),
        (Document(page_content="高热不退应就医"), 0.34),
    ]
    monkeypatch.setattr(vectors, "_get_store", lambda: fake_store)

    res = await vectors.search_guidelines("感冒 治疗", k=2)
    assert [c.text for c in res] == ["感冒应多休息多饮水", "高热不退应就医"]
    assert res[0].score == 0.12


@pytest.mark.asyncio
async def test_search_guidelines_degrades_on_error(monkeypatch):
    def boom():
        raise RuntimeError("pgvector down")
    monkeypatch.setattr(vectors, "_get_store", boom)
    assert await vectors.search_guidelines("x") == []
