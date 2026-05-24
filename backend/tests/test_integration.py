import os
# Set dummy API key before importing app to avoid initialization errors
os.environ["OPENAI_API_KEY"] = "sk-test-dummy-key-for-testing"

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_full_diagnosis_flow(client):
    """测试完整的诊断流程"""
    # Mock responses for two rounds of conversation
    mock_result_round1 = {
        "messages": [
            {"role": "user", "content": "我最近三天一直头痛，还有点发烧"},
            {"role": "assistant", "content": "您好，我理解您最近有头痛和发烧的症状。请问您的体温大概是多少度？"}
        ],
        "symptoms": ["头痛", "发烧"],
        "current_stage": "analyzing",
        "need_more_info": True,
        "possible_diseases": [],
        "treatment_plan": ""
    }

    mock_result_round2 = {
        "messages": [
            {"role": "user", "content": "我最近三天一直头痛，还有点发烧"},
            {"role": "assistant", "content": "您好，我理解您最近有头痛和发烧的症状。请问您的体温大概是多少度？"},
            {"role": "user", "content": "体温大概38度，没有其他症状"},
            {"role": "assistant", "content": "根据您的症状，您可能患有上呼吸道感染。建议多休息、多喝水，如症状加重请及时就医。"}
        ],
        "symptoms": ["头痛", "发烧"],
        "current_stage": "completed",
        "need_more_info": False,
        "possible_diseases": ["上呼吸道感染"],
        "treatment_plan": "多休息、多喝水，如症状加重请及时就医"
    }

    call_count = 0

    async def mock_ainvoke(state):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_result_round1
        return mock_result_round2

    with patch("app.routers.chat.medical_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(side_effect=mock_ainvoke)

        # 第一轮：发送症状
        response1 = await client.post("/api/chat", json={
            "message": "我最近三天一直头痛，还有点发烧"
        })
        assert response1.status_code == 200
        data1 = response1.json()
        session_id = data1["session_id"]
        assert session_id is not None
        assert "reply" in data1
        assert data1["stage"] == "analyzing"

        # 第二轮：回答追问
        response2 = await client.post("/api/chat", json={
            "message": "体温大概38度，没有其他症状",
            "session_id": session_id
        })
        assert response2.status_code == 200
        data2 = response2.json()
        assert "reply" in data2
        assert data2["stage"] == "completed"

        # 验证历史记录
        history = await client.get(f"/api/history/{session_id}")
        assert history.status_code == 200
        history_data = history.json()
        assert len(history_data["messages"]) >= 4  # 至少2轮对话
