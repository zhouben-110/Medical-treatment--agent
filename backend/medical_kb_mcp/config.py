from functools import lru_cache
from pydantic_settings import BaseSettings


class MCPSettings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medical_agent"
    llm_api_key: str = ""              # DashScope API key (same .env var the app uses)
    embedding_model: str = "text-embedding-v3"
    data_dir: str = "./data"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def psycopg_url(self) -> str:
        """psycopg (sync) connection string for PGVector."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache()
def get_mcp_settings() -> MCPSettings:
    return MCPSettings()
