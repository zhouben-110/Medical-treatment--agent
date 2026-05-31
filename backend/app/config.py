from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Medical Agent"
    database_url: str = "sqlite+aiosqlite:///./medical_agent.db"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v3"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chroma_persist_dir: str = "./chroma_db"
    data_dir: str = "./data"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()
