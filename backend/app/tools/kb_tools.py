"""诊断 Agent 的自主检索工具集。

每个工具包装一个 medical_kb_mcp 原语，并附带 Redis 缓存与超时保护。
注意：docstring 会被 bind_tools 直接作为 prompt 发给模型，因此除了签名，
还必须说明「什么时候用」以及「返回值怎么解读」。
"""

import asyncio
import hashlib
import json
import logging

from langchain_core.tools import tool

from app.services.kb_service import (
    search_diseases_by_symptoms as _search_diseases,
    get_disease_detail as _get_detail,
    search_guidelines as _search_guidelines,
)
from app.redis import cache_get, cache_set

logger = logging.getLogger(__name__)

TOOL_TIMEOUT = 10  # 单次工具调用上限（秒）
SUBMIT_TOOL_NAME = "submit_diagnosis"


def _cache_key(name: str, payload: dict) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]
    return f"mc:tool:{name}:{digest}"


async def _cached_call(name: str, payload: dict, factory, ttl: int, empty):
    """按工具粒度缓存 + 超时 + 失败降级为 empty（不抛给 Agent 循环）。"""
    key = _cache_key(name, payload)
    cached = await cache_get(key)
    if cached is not None:
        return cached

    try:
        result = await asyncio.wait_for(factory(), timeout=TOOL_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(f"[tool] {name} 超时（{TOOL_TIMEOUT}s）")
        return empty
    except Exception as e:
        logger.error(f"[tool] {name} 调用失败: {e}", exc_info=True)
        return empty

    if result:
        await cache_set(key, result, ttl=ttl)
    return result


@tool
async def search_diseases(symptoms: list[str], limit: int = 5) -> list[dict]:
    """根据症状列表检索候选疾病。

    使用时机：诊断的第一步。已收集到症状、需要知道有哪些候选疾病时调用。
    通常先用它拿到疾病名，再用 get_disease_detail 查具体治疗方案。

    Args:
        symptoms: 症状列表，如 ["发热", "咳嗽", "咽痛"]。传得越完整匹配越准。
        limit: 候选数量，默认 5；症状很明确时可减到 3。

    Returns:
        每项含 name / match_score / severity / description。
        match_score 为混合评分（语义相似度 0.6 + 症状交集 0.4）：
        > 0.6 才值得进一步查详情；若全部低于 0.4，说明知识库没有匹配，
        应如实告知用户无法判断，绝不要凭记忆推测疾病。
    """
    async def _run():
        matches = await _search_diseases(symptoms, limit)
        return [m.model_dump() for m in matches]

    return await _cached_call(
        "search_diseases", {"symptoms": symptoms, "limit": limit},
        _run, ttl=3600, empty=[],
    )


@tool
async def get_disease_detail(name: str) -> dict | None:
    """查询单个疾病的完整档案（治疗方案、就医指征、典型症状）。

    使用时机：已通过 search_diseases 拿到候选疾病名之后，需要给出
    具体用药与治疗建议时调用。一次只查一个病；要查多个就多次调用。

    Args:
        name: 疾病全名，必须与 search_diseases 返回的 name 完全一致，
              不要自行改写或简称。

    Returns:
        含 name / symptoms / description / treatment / when_to_see_doctor / severity。
        返回 None 表示知识库中没有该疾病，此时不要编造治疗方案。
    """
    async def _run():
        detail = await _get_detail(name)
        return detail.model_dump() if detail else None

    return await _cached_call(
        "get_disease_detail", {"name": name},
        _run, ttl=86400, empty=None,
    )


@tool
async def search_guidelines(query: str, k: int = 3) -> list[dict]:
    """在诊疗指南文献库中做语义检索。

    使用时机：症状不典型、候选疾病评分相近难以区分、或需要权威文献
    支撑用药建议时调用。若 search_diseases 已给出高分明确结果，
    通常不必再查指南。

    Args:
        query: 自然语言检索语句，如「儿童发热用药注意事项」。
               用完整描述而非孤立关键词，检索效果更好。
        k: 返回片段数，默认 3。

    Returns:
        每项含 text（指南原文片段）与来源元数据。返回空列表表示
        指南库无相关内容，此时应基于 search_diseases 的结果作答。
    """
    async def _run():
        chunks = await _search_guidelines(query, k)
        return [c.model_dump() for c in chunks]

    return await _cached_call(
        "search_guidelines", {"query": query, "k": k},
        _run, ttl=3600, empty=[],
    )


@tool
def submit_diagnosis(
    possible_diseases: list[str],
    reasoning: str,
    treatment_advice: str,
    need_doctor: bool,
) -> str:
    """提交最终诊断结论，结束本轮诊断。

    调用前提：必须已经通过 search_diseases / get_disease_detail /
    search_guidelines 至少获得一次有效的知识库返回结果。
    禁止在没有任何工具返回结果的情况下调用本工具。

    若知识库确实没有匹配内容，仍然调用本工具，但在 reasoning 中
    明确说明「知识库无匹配依据」，并在 need_doctor 中填 true。

    Args:
        possible_diseases: 候选疾病名，按可能性从高到低排序。
                           必须来自知识库返回结果，不可自行添加。
        reasoning: 判断依据。必须引用工具返回的具体内容
                   （如匹配评分、指南片段），不要只写「根据症状判断」。
        treatment_advice: 治疗与调理建议，包含用药、生活注意事项。
        need_doctor: 是否建议就医。拿不准时填 true。
    """
    return "诊断已提交"


KB_TOOLS = [search_diseases, get_disease_detail, search_guidelines, submit_diagnosis]
RETRIEVAL_TOOLS = [search_diseases, get_disease_detail, search_guidelines]
RETRIEVAL_TOOL_NAMES = {t.name for t in RETRIEVAL_TOOLS}

