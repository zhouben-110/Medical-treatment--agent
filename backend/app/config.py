from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    app_name: str = "Medical Agent"
    environment: str = "development"  # "development" | "testing" | "production"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medical_agent"
    llm_api_key: str = ""
    llm_api_keys: str = ""  # 逗号分隔的 Key 列表，支持随机轮询
    llm_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # 灾备大模型配置
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = "qwen-turbo"
    llm_fallback_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    embedding_model: str = "text-embedding-v3"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    data_dir: str = "./data"
    api_key: str = ""
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"]
    sql_echo: bool = False
    mcp_server_url: str = "http://localhost:8765/mcp"
    redis_url: str = "redis://localhost:6379/0"

    # 诊断管线选择：False=固定管线（diagnose_and_advise），True=自主 Agent 循环
    enable_agent_diagnose: bool = False

    # Supabase 配置
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""  # 在 Supabase Dashboard > Settings > API > JWT Secret 获取

    # 本地 JWT 配置
    jwt_secret: str = "your-custom-jwt-secret-key-change-this-in-production"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()
