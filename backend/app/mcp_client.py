"""Thin MCP client: connects the app to the Medical-KB MCP server."""

from langchain_mcp_adapters.client import MultiServerMCPClient
from app.config import get_settings


async def _load_tools() -> list:
    settings = get_settings()
    client = MultiServerMCPClient({
        "medical_kb": {"transport": "streamable_http", "url": settings.mcp_server_url},
    })
    return await client.get_tools()


async def load_tools() -> list:
    """Return the MCP tools, or [] if the server is unreachable (graceful degrade)."""
    try:
        return await _load_tools()
    except Exception as e:
        print(f"[mcp_client] could not load MCP tools: {e}")
        return []


def get_tool(tools: list, name: str):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t
    return None
