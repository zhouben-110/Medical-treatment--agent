import pytest
from unittest.mock import AsyncMock, patch
from app.rag.retriever import MedicalRetriever


def _disease_match(name="普通感冒", score=0.8, severity="轻"):
    return {
        "name": name,
        "matched_symptoms": ["发热"],
        "match_score": score,
        "severity": severity,
        "description": "上感",
    }


def _disease_detail(name="普通感冒"):
    return {
        "name": name,
        "description": "上感",
        "treatment": "对症处理",
        "when_to_see_doctor": "高热不退",
        "severity": "轻",
        "symptoms": ["发热"],
    }


def _guideline_chunk(text="多休息多饮水", score=0.1):
    return {
        "text": text,
        "score": score,
    }


@pytest.mark.asyncio
async def test_retrieve_for_diagnosis_formats_context():
    r = MedicalRetriever()
    with (
        patch.object(r, "_search_diseases_cached", AsyncMock(return_value=[_disease_match()])),
        patch.object(r, "_search_guidelines_cached", AsyncMock(return_value=[_guideline_chunk()])),
    ):
        ctx, names = await r.retrieve_for_diagnosis(["发热"])
    assert "普通感冒" in ctx
    assert "多休息多饮水" in ctx
    assert names == ["普通感冒"]


@pytest.mark.asyncio
async def test_retrieve_for_advice_formats_detail():
    r = MedicalRetriever()
    with (
        patch.object(r, "_get_detail_cached", AsyncMock(return_value=_disease_detail())),
        patch.object(r, "_search_guidelines_cached", AsyncMock(return_value=[_guideline_chunk("多休息")])),
    ):
        ctx = await r.retrieve_for_advice(["普通感冒"], ["发热"])
    assert "普通感冒" in ctx
    assert "对症处理" in ctx


@pytest.mark.asyncio
async def test_retrieve_handles_empty_results():
    r = MedicalRetriever()
    with (
        patch.object(r, "_search_diseases_cached", AsyncMock(return_value=[])),
        patch.object(r, "_search_guidelines_cached", AsyncMock(return_value=[])),
    ):
        ctx, names = await r.retrieve_for_diagnosis(["发热"])
    assert ctx == ""
    assert names == []


@pytest.mark.asyncio
async def test_retrieve_degrades_on_exception():
    r = MedicalRetriever()
    with (
        patch("app.rag.retriever.get_disease_detail", AsyncMock(side_effect=RuntimeError("db down"))),
        patch("app.rag.retriever.search_guidelines", AsyncMock(side_effect=RuntimeError("db down"))),
    ):
        # Exceptions from kb_service functions are caught internally, gracefully returning empty
        assert await r.retrieve_for_advice(["普通感冒"], ["发热"]) == ""
