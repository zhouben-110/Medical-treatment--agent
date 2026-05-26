import os
# Set dummy API key before importing app to avoid initialization errors
os.environ["OPENAI_API_KEY"] = "sk-test-dummy-key-for-testing"

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _snap(values=None, created_at=None):
    s = MagicMock()
    s.created_at = created_at
    s.values = values or {}
    return s


@pytest.mark.asyncio
async def test_full_diagnosis_flow(client):
    """测试完整的诊断流程：第一轮追问 → 第二轮诊断完成"""
    ai_question = AIMessage(content="您好，我理解您最近有头痛和发烧的症状。请问您的体温大概是多少度？")
    ai_advice = AIMessage(content="根据您的症状，您可能患有上呼吸道感染。建议多休息、多喝水，如症状加重请及时就医。")

    round1 = {
        "messages": [ai_question],
        "symptoms": ["头痛", "发烧"],
        "current_stage": "questioning",
        "need_more_info": True,
        "possible_diseases": [],
        "treatment_plan": "",
    }
    round2 = {
        "messages": [ai_advice],
        "symptoms": ["头痛", "发烧"],
        "current_stage": "completed",
        "need_more_info": False,
        "possible_diseases": ["上呼吸道感染"],
        "treatment_plan": "多休息、多喝水，如症状加重请及时就医",
    }

    # aget_state 在两次请求里各调用一次：第一次新会话 created_at=None,
    # 第二次续聊 created_at 是个时间戳
    snapshots = iter([
        _snap(created_at=None),
        _snap(created_at=datetime.now()),
    ])
    results = iter([round1, round2])

    with patch("app.graph.medical_graph") as mock_graph:
        mock_graph.aget_state = AsyncMock(side_effect=lambda *a, **kw: next(snapshots))
        mock_graph.ainvoke = AsyncMock(side_effect=lambda *a, **kw: next(results))

        # 第一轮：发送症状
        response1 = await client.post("/api/chat", json={
            "message": "我最近三天一直头痛，还有点发烧"
        })
        assert response1.status_code == 200
        data1 = response1.json()
        session_id = data1["session_id"]
        assert session_id is not None
        assert data1["stage"] == "questioning"
        assert data1["need_more_info"] is True

        # 第二轮：回答追问
        response2 = await client.post("/api/chat", json={
            "message": "体温大概38度，没有其他症状",
            "session_id": session_id
        })
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["stage"] == "completed"
        assert data2["need_more_info"] is False
        assert "上呼吸道感染" in data2["possible_diseases"]

        # 验证历史记录：2 user + 2 assistant
        history = await client.get(f"/api/history/{session_id}")
        assert history.status_code == 200
        history_data = history.json()
        assert len(history_data["messages"]) >= 4
