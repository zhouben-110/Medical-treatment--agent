"""Triage agent 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.nodes.triage import (
    _check_red_flags,
    run_triage,
    RED_FLAG_KEYWORDS,
    EMERGENCY_RESPONSE,
    TriageResult,
)


# ── 确定性红旗关键词检测 ──────────────────────────────────────

class TestRedFlagDetection:
    def test_chest_pain(self):
        assert "胸痛" in _check_red_flags("胸痛剧烈")

    def test_breathing_difficulty(self):
        assert "呼吸困难" in _check_red_flags("感觉呼吸困难，喘不上气")

    def test_stroke_symptoms(self):
        flags = _check_red_flags("突然一侧肢体无力，嘴角歪斜")
        assert "一侧肢体无力" in flags
        assert "嘴角歪斜" in flags

    def test_bleeding(self):
        assert "呕血" in _check_red_flags("刚才呕血了")

    def test_anaphylaxis(self):
        assert "过敏性休克" in _check_red_flags("怀疑过敏性休克")

    def test_high_fever(self):
        flags = _check_red_flags("体温40度，高热不退")
        assert "高热不退" in flags
        assert "体温40" in flags

    def test_no_red_flags(self):
        assert _check_red_flags("头疼，有点发烧") == []

    def test_empty_message(self):
        assert _check_red_flags("") == []

    def test_all_keywords_in_message(self):
        # 极端情况：所有关键词都在一条消息里
        msg = "、".join(RED_FLAG_KEYWORDS)
        flags = _check_red_flags(msg)
        assert len(flags) == len(RED_FLAG_KEYWORDS)


# ── TriageResult Pydantic 模型 ────────────────────────────────

class TestTriageResult:
    def test_emergency_result(self):
        r = TriageResult(
            is_emergency=True,
            red_flags=["胸痛"],
            action="emergency_short_circuit",
            reason="疑似心梗",
        )
        assert r.is_emergency is True
        assert r.action == "emergency_short_circuit"

    def test_normal_result(self):
        r = TriageResult(
            is_emergency=False,
            action="continue_normal_flow",
            reason="普通感冒症状",
        )
        assert r.is_emergency is False
        assert r.red_flags == []

    def test_missing_action_raises(self):
        with pytest.raises(Exception):
            TriageResult(is_emergency=True, reason="test")


# ── run_triage 节点集成测试 ───────────────────────────────────

def _make_state(user_message: str, symptoms: list[str] | None = None) -> dict:
    """构造测试用的 state"""
    return {
        "messages": [{"role": "user", "content": user_message}],
        "symptoms": symptoms or [],
        "current_stage": "start",
        "is_emergency": False,
        "red_flags": [],
        "emergency_message": "",
    }


@pytest.mark.asyncio
async def test_triage_red_flag_short_circuit():
    """红旗关键词命中 → 直接急救短路，不调 LLM"""
    state = _make_state("我胸口剧烈疼痛，呼吸困难")
    result = await run_triage(state)

    assert result["is_emergency"] is True
    assert result["current_stage"] == "emergency"
    assert "胸痛" in result["red_flags"] or "呼吸困难" in result["red_flags"]
    assert result["emergency_message"] == EMERGENCY_RESPONSE
    # 确认消息已添加
    assert len(result["messages"]) == 1
    assert "120" in result["messages"][0]["content"]


@pytest.mark.asyncio
async def test_triage_normal_flow_no_red_flags():
    """无红旗症状 → LLM 分诊判断为非紧急"""
    mock_result = TriageResult(
        is_emergency=False,
        red_flags=[],
        action="continue_normal_flow",
        reason="普通感冒症状",
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.nodes.triage.get_llm", return_value=mock_llm), \
         patch("app.nodes.triage.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        # prompt | llm → mock chain that returns mock_result
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        state = _make_state("头疼，有点流鼻涕")
        result = await run_triage(state)

    assert result["is_emergency"] is False
    assert result["current_stage"] == "triaged"
    assert "emergency_message" not in result


@pytest.mark.asyncio
async def test_triage_llm_emergency():
    """LLM 判断为紧急（关键词未覆盖的情况）"""
    mock_result = TriageResult(
        is_emergency=True,
        red_flags=["严重脱水"],
        action="emergency_short_circuit",
        reason="严重脱水可能导致休克",
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.nodes.triage.get_llm", return_value=mock_llm), \
         patch("app.nodes.triage.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        state = _make_state("腹泻三天，已经站不起来了")
        result = await run_triage(state)

    assert result["is_emergency"] is True
    assert result["current_stage"] == "emergency"
    assert "严重脱水" in result["red_flags"]


@pytest.mark.asyncio
async def test_triage_llm_failure_graceful():
    """LLM 调用失败时默认非紧急，不阻塞流程"""
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.nodes.triage.get_llm", return_value=mock_llm), \
         patch("app.nodes.triage.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)

        state = _make_state("有点不舒服")
        result = await run_triage(state)

    assert result["is_emergency"] is False
    assert result["current_stage"] == "triaged"
