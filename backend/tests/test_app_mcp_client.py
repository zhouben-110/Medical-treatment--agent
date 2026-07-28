import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")

import pytest
from unittest.mock import AsyncMock, patch
from app import mcp_client


def test_get_tool_returns_by_name():
    tool_a = type("T", (), {"name": "search_guidelines"})()
    tool_b = type("T", (), {"name": "get_disease_detail"})()
    tools = [tool_a, tool_b]
    assert mcp_client.get_tool(tools, "get_disease_detail") is tool_b
    assert mcp_client.get_tool(tools, "nope") is None


@pytest.mark.asyncio
async def test_load_tools_graceful_degrade():
    with patch("app.mcp_client.MultiServerMCPClient") as mock_client_cls:
        mock_client_cls.side_effect = RuntimeError("connection failed")
        tools = await mcp_client.load_tools()
        assert tools == []
