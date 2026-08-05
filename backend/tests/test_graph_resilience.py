import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.graph import supervisor_node, STAGE_ALLOWED
from app.routers.chat import _build_graph_input, VALID_STAGES
from app.nodes.questioner import generate_question, FALLBACK_QUESTION
from app.nodes.diagnose_and_advise import diagnose_and_advise


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-api-key")


@pytest.mark.asyncio
async def test_supervisor_out_of_bounds_route_fallback():
    """测试 Supervisor 输出越界路由（漏洞1：analyzing 阶段误输出 analyze）时回退确定性路由"""
    state = {
        "current_stage": "analyzing",
        "symptoms": ["头痛", "发热"],
        "need_more_info": True,
        "messages": [{"role": "user", "content": "我头痛发热"}]
    }

    mock_llm_response = MagicMock()
    mock_llm_response.content = "analyze"

    mock_chain = AsyncMock()
    mock_chain.ainvoke.return_value = mock_llm_response

    with patch("app.graph.get_llm") as mock_get_llm, \
         patch("app.graph.ChatPromptTemplate.from_template", return_value=mock_chain):
        mock_get_llm.return_value = MagicMock()

        res = await supervisor_node(state)
        # 应当被 STAGE_ALLOWED 拦下，回退为确定性路由 "supervisor:question" 绝不重入 analyze
        assert res["current_stage"] == "supervisor:question"


@pytest.mark.asyncio
async def test_supervisor_llm_exception_fallback():
    """测试 Supervisor LLM 异常抛出时优雅回退确定性路由"""
    state = {
        "current_stage": "analyzing",
        "symptoms": ["咳嗽"],
        "need_more_info": False,
        "messages": [{"role": "user", "content": "咳嗽三天"}]
    }

    mock_chain = AsyncMock()
    mock_chain.ainvoke.side_effect = RuntimeError("LLM API Timeout")

    with patch("app.graph.get_llm") as mock_get_llm, \
         patch("app.graph.ChatPromptTemplate.from_template", return_value=mock_chain):
        mock_get_llm.return_value = MagicMock()

        res = await supervisor_node(state)
        assert res["current_stage"] == "supervisor:diagnose"


def test_build_graph_input_stage_normalization():
    """测试漏洞5：残留坏状态 (如 supervisor:analyze) 自动归一化重置为 start"""
    graph_input = _build_graph_input(
        user_message="头晕怎么回事",
        session_id="session-123",
        is_new=False,
        current_stage="supervisor:analyze",
        prev_state={"symptoms": ["头晕"]}
    )

    assert graph_input["current_stage"] == "start"
    assert graph_input["symptoms"] == ["头晕"]


@pytest.mark.asyncio
async def test_questioner_llm_failure_fallback():
    """测试漏洞4：questioner 节点 LLM 崩溃时降级为通用追问，不抛出异常"""
    state = {
        "symptoms": ["腹泻"],
        "messages": [{"role": "user", "content": "拉肚子"}]
    }

    mock_chain = AsyncMock()
    mock_chain.ainvoke.side_effect = Exception("Service Unavailable")

    with patch("app.nodes.questioner.get_llm") as mock_get_llm, \
         patch("app.nodes.questioner.ChatPromptTemplate.from_template", return_value=mock_chain):
        mock_get_llm.return_value = MagicMock()

        res = await generate_question(state)
        assert res["current_stage"] == "questioning"
        assert res["messages"][0]["content"] == FALLBACK_QUESTION


@pytest.mark.asyncio
async def test_diagnose_and_advise_llm_failure_fallback():
    """测试漏洞4：diagnose_and_advise 节点 LLM 崩溃时降级为安全文案"""
    state = {
        "symptoms": ["胸痛"],
        "messages": [{"role": "user", "content": "胸痛"}]
    }

    mock_chain = AsyncMock()
    mock_chain.ainvoke.side_effect = Exception("LLM Error")

    with patch("app.nodes.diagnose_and_advise.get_llm") as mock_get_llm, \
         patch("app.nodes.diagnose_and_advise.ChatPromptTemplate.from_template", return_value=mock_chain):
        mock_get_llm.return_value = MagicMock()

        res = await diagnose_and_advise(state)
        assert res["current_stage"] == "completed"
        assert "基于您提供的症状，系统暂时无法生成具体的诊断建议" in res["treatment_plan"]
