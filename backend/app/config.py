from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Medical Agent"
    database_url: str = "sqlite+aiosqlite:///./medical_agent.db"
    openai_api_key: str = ""
    openai_model: str = "gpt-4"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
