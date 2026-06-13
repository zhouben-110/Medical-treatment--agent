import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")

import pytest
from unittest.mock import AsyncMock, patch
from medical_kb_mcp.db import DiseaseMatch, DiseaseDetail
from medical_kb_mcp.vectors import GuidelineChunk
from app.rag.retriever import MedicalRetriever


def _disease_match(name="普通感冒", score=0.8, severity="轻"):
    return DiseaseMatch(
        name=name, matched_symptoms=["发热"], match_score=score,
        severity=severity, description="上感",
    )


def _disease_detail(name="普通感冒"):
    return DiseaseDetail(
        name=name, description="上感", treatment="对症处理",
        when_to_see_doctor="高热不退", severity="轻", symptoms=["发热"],
    )


def _guideline_chunk(text="多休息多饮水", score=0.1):
    return GuidelineChunk(text=text, score=score)


@pytest.mark.asyncio
@patch("app.rag.retriever.search_guidelines", new_callable=AsyncMock)
@patch("app.rag.retriever.search_diseases_by_symptoms", new_callable=AsyncMock)
async def test_retrieve_for_diagnosis_formats_context(mock_diseases, mock_guidelines):
    mock_diseases.return_value = [_disease_match()]
    mock_guidelines.return_value = [_guideline_chunk()]
    r = MedicalRetriever()
    ctx = await r.retrieve_for_diagnosis(["发热"])
    assert "普通感冒" in ctx
    assert "多休息多饮水" in ctx


@pytest.mark.asyncio
@patch("app.rag.retriever.search_guidelines", new_callable=AsyncMock)
@patch("app.rag.retriever.get_disease_detail", new_callable=AsyncMock)
async def test_retrieve_for_advice_formats_detail(mock_detail, mock_guidelines):
    mock_detail.return_value = _disease_detail()
    mock_guidelines.return_value = [_guideline_chunk("多休息")]
    r = MedicalRetriever()
    ctx = await r.retrieve_for_advice(["普通感冒"], ["发热"])
    assert "普通感冒" in ctx
    assert "对症处理" in ctx


@pytest.mark.asyncio
@patch("app.rag.retriever.search_guidelines", new_callable=AsyncMock)
@patch("app.rag.retriever.search_diseases_by_symptoms", new_callable=AsyncMock)
async def test_retrieve_handles_empty_results(mock_diseases, mock_guidelines):
    mock_diseases.return_value = []
    mock_guidelines.return_value = []
    r = MedicalRetriever()
    assert await r.retrieve_for_diagnosis(["发热"]) == ""


@pytest.mark.asyncio
@patch("app.rag.retriever.search_guidelines", new_callable=AsyncMock)
@patch("app.rag.retriever.get_disease_detail", new_callable=AsyncMock)
async def test_retrieve_degrades_on_exception(mock_detail, mock_guidelines):
    mock_detail.side_effect = RuntimeError("db down")
    mock_guidelines.side_effect = RuntimeError("db down")
    r = MedicalRetriever()
    assert await r.retrieve_for_advice(["普通感冒"], ["发热"]) == ""
