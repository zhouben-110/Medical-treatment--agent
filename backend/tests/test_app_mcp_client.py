import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")

import pytest
from unittest.mock import AsyncMock, patch
from app import mcp_client


@pytest.mark.asyncio
async def test_get_tool_returns_by_name():
    tool_a = type("T", (), {"name": "search_guidelines"})()
    tool_b = type("T", (), {"name": "get_disease_detail"})()
    with patch.object(mcp_client, "_load_tools", AsyncMock(return_value=[tool_a, tool_b])):
        tools = await mcp_client.load_tools()
        assert mcp_client.get_tool(tools, "get_disease_detail") is tool_b
        assert mcp_client.get_tool(tools, "nope") is None
