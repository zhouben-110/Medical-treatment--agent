"""Thin MCP client: connects the app to the Medical-KB MCP server."""

import sys
from langchain_mcp_adapters.client import MultiServerMCPClient

# Keep client alive for the app lifetime; tools hold a ref to its session.
_client: MultiServerMCPClient | None = None


async def load_tools() -> list:
    """Connect to MCP server via stdio and return tools. Gracefully degrades to []."""
    global _client
    try:
        _client = MultiServerMCPClient({
            "medical_kb": {
                "transport": "stdio",
                "command": sys.executable,
                "args": ["-m", "medical_kb_mcp.server", "stdio"],
            },
        })
        return await _client.get_tools()
    except Exception as e:
        print(f"[mcp_client] could not load MCP tools: {e}")
        _client = None
        return []


def get_tool(tools: list, name: str):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t
    return None
