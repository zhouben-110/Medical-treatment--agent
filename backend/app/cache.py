"""诊断结果缓存：相似症状组合复用诊断结果"""

import time
from typing import Optional

# 内存缓存：key 为排序后的症状元组，value 为 (result, timestamp)
_cache: dict[tuple, tuple[dict, float]] = {}
MAX_CACHE_SIZE = 200
CACHE_TTL = 3600  # 1 小时过期


def _make_key(symptoms: list[str]) -> tuple:
    return tuple(sorted(s.strip() for s in symptoms if s.strip()))


def get_cached_diagnosis(symptoms: list[str]) -> Optional[dict]:
    """查询缓存的诊断结果"""
    key = _make_key(symptoms)
    entry = _cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > CACHE_TTL:
        del _cache[key]
        return None
    return result


def cache_diagnosis(symptoms: list[str], result: dict):
    """缓存诊断结果"""
    global _cache
    key = _make_key(symptoms)
    # 简单淘汰：超过上限清空最旧的一半
    if len(_cache) >= MAX_CACHE_SIZE:
        sorted_keys = sorted(_cache.keys(), key=lambda k: _cache[k][1])
        for k in sorted_keys[:MAX_CACHE_SIZE // 2]:
            del _cache[k]
    _cache[key] = (result, time.time())
