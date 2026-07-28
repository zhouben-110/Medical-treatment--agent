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
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer mock-token-user"}
    ) as ac:
        yield ac


def _snap(values=None, created_at=None):
    s = MagicMock()
    s.created_at = created_at
    s.values = values or {}
    return s


@pytest.mark.asyncio
async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Medical Agent API"}


@pytest.mark.asyncio
async def test_get_symptoms(client):
    response = await client.get("/api/symptoms")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data


@pytest.mark.asyncio
async def test_chat(client):
    mock_result = {
        "messages": [AIMessage(content="您好，请问头痛持续多久了？")],
        "symptoms": ["头痛"],
        "current_stage": "questioning",
        "need_more_info": True,
        "possible_diseases": [],
        "treatment_plan": "",
    }
    with patch("app.graph.medical_graph") as mock_graph:
        mock_graph.aget_state = AsyncMock(return_value=_snap(created_at=None))
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        response = await client.post("/api/chat", json={
            "message": "我最近总是头痛"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "session_id" in data
        assert data["stage"] == "questioning"
        assert data["need_more_info"] is True


@pytest.mark.asyncio
async def test_get_history(client):
    response = await client.get("/api/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
