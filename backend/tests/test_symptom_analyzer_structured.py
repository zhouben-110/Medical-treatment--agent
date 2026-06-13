"""Symptom analyzer 结构化输出测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.nodes.symptom_analyzer import SymptomExtraction, analyze_symptoms


# ── SymptomExtraction Pydantic 模型 ──────────────────────────

class TestSymptomExtraction:
    def test_valid_extraction(self):
        r = SymptomExtraction(
            symptoms=["头疼", "发烧"],
            severity="中度",
            need_more_info=True,
        )
        assert r.symptoms == ["头疼", "发烧"]
        assert r.severity == "中度"
        assert r.need_more_info is True

    def test_empty_symptoms(self):
        r = SymptomExtraction(symptoms=[], severity="轻度", need_more_info=False)
        assert r.symptoms == []

    def test_invalid_severity_raises(self):
        with pytest.raises(Exception):
            SymptomExtraction(symptoms=["头疼"], severity="极重", need_more_info=False)

    def test_severity_values(self):
        for sev in ["轻度", "中度", "重度"]:
            r = SymptomExtraction(symptoms=["test"], severity=sev, need_more_info=False)
            assert r.severity == sev


# ── analyze_symptoms 节点测试 ─────────────────────────────────

def _make_state(user_message: str, existing: list[str] | None = None) -> dict:
    return {
        "messages": [{"role": "user", "content": user_message}],
        "symptoms": existing or [],
        "current_stage": "triaged",
        "need_more_info": True,
    }


@pytest.mark.asyncio
async def test_analyze_extracts_new_symptoms():
    """结构化输出正确提取新症状"""
    mock_result = SymptomExtraction(
        symptoms=["咳嗽", "流鼻涕"],
        severity="轻度",
        need_more_info=True,
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.nodes.symptom_analyzer.get_llm", return_value=mock_llm), \
         patch("app.nodes.symptom_analyzer.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        state = _make_state("我有点咳嗽，还流鼻涕")
        result = await analyze_symptoms(state)

    assert result["symptoms"] == ["咳嗽", "流鼻涕"]
    assert result["need_more_info"] is True
    assert result["current_stage"] == "analyzing"


@pytest.mark.asyncio
async def test_analyze_merges_with_existing_symptoms():
    """新症状与已有症状合并去重"""
    mock_result = SymptomExtraction(
        symptoms=["咳嗽", "发烧"],
        severity="中度",
        need_more_info=False,
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.nodes.symptom_analyzer.get_llm", return_value=mock_llm), \
         patch("app.nodes.symptom_analyzer.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        state = _make_state("还是咳嗽，发烧了", existing=["咳嗽", "头疼"])
        result = await analyze_symptoms(state)

    # "咳嗽" 已存在，应该只出现一次
    assert result["symptoms"].count("咳嗽") == 1
    # 顺序保持：先已有，再新增
    assert result["symptoms"][0] == "咳嗽"
    assert "发烧" in result["symptoms"]
    assert "头疼" in result["symptoms"]


@pytest.mark.asyncio
async def test_analyze_no_new_symptoms():
    """用户消息未提及新症状"""
    mock_result = SymptomExtraction(
        symptoms=[],
        severity="轻度",
        need_more_info=True,
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.nodes.symptom_analyzer.get_llm", return_value=mock_llm), \
         patch("app.nodes.symptom_analyzer.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        state = _make_state("今天天气不错", existing=["头疼"])
        result = await analyze_symptoms(state)

    assert result["symptoms"] == ["头疼"]
    assert result["need_more_info"] is True


@pytest.mark.asyncio
async def test_analyze_llm_failure_preserves_state():
    """LLM 调用失败时保留已有状态"""
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("timeout"))

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.nodes.symptom_analyzer.get_llm", return_value=mock_llm), \
         patch("app.nodes.symptom_analyzer.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("timeout"))
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        state = _make_state("头疼", existing=["发烧"])
        result = await analyze_symptoms(state)

    # 失败时只更新 stage，不改变其他字段
    assert result["current_stage"] == "analyzing"
    assert "symptoms" not in result
