"""诊断结果缓存：相似症状组合复用诊断结果（LRU 策略）"""

import time
from typing import Optional
from collections import OrderedDict

MAX_CACHE_SIZE = 200
CACHE_TTL = 3600  # 1 小时过期

# LRU 缓存：key 为排序后的症状元组，value 为 (result, timestamp)
_cache: OrderedDict[tuple, tuple[dict, float]] = OrderedDict()


def _make_key(symptoms: list[str]) -> tuple:
    return tuple(sorted(s.strip() for s in symptoms if s.strip()))


def get_cached_diagnosis(symptoms: list[str]) -> Optional[dict]:
    """查询缓存的诊断结果"""
    key = _make_key(symptoms)
    entry = _cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    # 检查是否过期
    if time.time() - ts > CACHE_TTL:
        del _cache[key]
        return None
    # 移到末尾（最近使用）
    _cache.move_to_end(key)
    return result


def cache_diagnosis(symptoms: list[str], result: dict):
    """缓存诊断结果，LRU 淘汰策略"""
    key = _make_key(symptoms)
    # 如果已存在，先删除再重新插入（移到末尾）
    if key in _cache:
        del _cache[key]
    # 超过上限时淘汰最久未使用的（头部）
    while len(_cache) >= MAX_CACHE_SIZE:
        _cache.popitem(last=False)
    _cache[key] = (result, time.time())
