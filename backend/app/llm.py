"""LLM 实例统一管理"""

from functools import lru_cache
from langchain_openai import ChatOpenAI
from app.config import get_settings


@lru_cache()
def get_llm(temperature: float = 0) -> ChatOpenAI:
    """获取 LLM 实例（带缓存，相同 temperature 复用同一实例）"""
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        temperature=temperature,
    )
