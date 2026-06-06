import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")

import json
import pytest
from unittest.mock import AsyncMock
from app.rag.retriever import MedicalRetriever


def _tool(name, items):
    """Mimic langchain-mcp-adapters: one text content block per returned item."""
    t = type("T", (), {})()
    t.name = name
    blocks = [{"type": "text", "text": json.dumps(it, ensure_ascii=False)} for it in items]
    t.ainvoke = AsyncMock(return_value=blocks)
    return t


@pytest.mark.asyncio
async def test_retrieve_for_diagnosis_formats_context():
    tools = [
        _tool("search_diseases_by_symptoms",
              [{"name": "普通感冒", "matched_symptoms": ["发热"], "match_score": 0.8,
                "severity": "轻", "description": "上感"}]),
        _tool("search_guidelines", [{"text": "多休息多饮水", "score": 0.1}]),
    ]
    r = MedicalRetriever(tools)
    ctx = await r.retrieve_for_diagnosis(["发热"])
    assert "普通感冒" in ctx
    assert "多休息多饮水" in ctx


@pytest.mark.asyncio
async def test_retrieve_for_advice_formats_detail():
    tools = [
        _tool("get_disease_detail",
              [{"name": "普通感冒", "description": "上感", "treatment": "对症处理",
                "when_to_see_doctor": "高热不退", "severity": "轻", "symptoms": ["发热"]}]),
        _tool("search_guidelines", [{"text": "多休息", "score": 0.1}]),
    ]
    r = MedicalRetriever(tools)
    ctx = await r.retrieve_for_advice(["普通感冒"], ["发热"])
    assert "普通感冒" in ctx
    assert "对症处理" in ctx


@pytest.mark.asyncio
async def test_retrieve_handles_empty_results():
    # Adapter returns [] when a tool finds nothing → context skips that section.
    tools = [
        _tool("search_diseases_by_symptoms", []),
        _tool("search_guidelines", []),
    ]
    r = MedicalRetriever(tools)
    assert await r.retrieve_for_diagnosis(["发热"]) == ""


@pytest.mark.asyncio
async def test_retrieve_degrades_when_tool_missing():
    r = MedicalRetriever([])           # no tools available (server down)
    assert await r.retrieve_for_diagnosis(["发热"]) == ""
    assert await r.retrieve_for_advice(["普通感冒"], ["发热"]) == ""
