import json
import pytest
from medical_kb_mcp import server as srv
from medical_kb_mcp.db import DiseaseMatch, DiseaseDetail
from medical_kb_mcp.vectors import GuidelineChunk


@pytest.mark.asyncio
async def test_lists_three_tools():
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    assert {"search_diseases_by_symptoms", "get_disease_detail", "search_guidelines"} <= names


@pytest.mark.asyncio
async def test_call_search_tool(monkeypatch):
    async def fake_search(symptoms, limit=5):
        return [DiseaseMatch(name="普通感冒", matched_symptoms=["发热"],
                             match_score=0.5, severity="轻", description="d")]
    monkeypatch.setattr(srv, "search_diseases_by_symptoms", fake_search)

    result = await srv.mcp.call_tool("search_diseases_by_symptoms", {"symptoms": ["发热"]})
    # FastMCP returns (content_blocks, structured_dict); assert the disease name appears
    assert "普通感冒" in json.dumps(result, default=str, ensure_ascii=False)
