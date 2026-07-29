"""LLM 实例统一管理"""

from functools import lru_cache
from langchain_openai import ChatOpenAI
from app.config import get_settings


def get_llm(temperature: float = 0):
    """获取 LLM 实例（带 Key 轮询与厂商/模型灾备 Fallbacks）"""
    settings = get_settings()
    primary_key = settings.llm_api_key

    # 1. 尝试从逗号分隔的 Key 列表中随机选择一个进行轮询
    if settings.llm_api_keys:
        import random
        keys = [k.strip() for k in settings.llm_api_keys.split(",") if k.strip()]
        if keys:
            primary_key = random.choice(keys)

    primary_llm = ChatOpenAI(
        api_key=primary_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        temperature=temperature,
        max_retries=2,  # 主模型重试 2 次
        timeout=30.0,
    )

    # 2. 如果配置了灾备大模型 Key，则使用 LangChain 的 with_fallbacks 自动切换机制
    fallback_key = settings.llm_fallback_api_key or primary_key
    if fallback_key:
        fallback_llm = ChatOpenAI(
            api_key=fallback_key,
            model=settings.llm_fallback_model,
            base_url=settings.llm_fallback_base_url,
            temperature=temperature,
            max_retries=1,  # 备用模型重试 1 次
            timeout=30.0,
        )
        return primary_llm.with_fallbacks([fallback_llm])

    return primary_llm
