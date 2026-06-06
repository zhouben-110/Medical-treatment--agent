def test_mcp_settings_reads_env(monkeypatch):
    monkeypatch.setenv("MCP_PORT", "9001")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/x")
    from medical_kb_mcp.config import MCPSettings
    s = MCPSettings()
    assert s.mcp_port == 9001
    assert s.database_url.endswith("/x")
    assert s.psycopg_url == "postgresql://u:p@localhost:5432/x"
    assert s.embedding_model  # has a default
