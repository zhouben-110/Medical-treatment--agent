from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    app_name: str = "Medical Agent"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medical_agent"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v3"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    data_dir: str = "./data"
    api_key: str = ""
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"]
    sql_echo: bool = False
    mcp_server_url: str = "http://localhost:8765/mcp"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()
