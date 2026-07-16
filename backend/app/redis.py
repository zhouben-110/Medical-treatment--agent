"""Redis 客户端：缓存、限流、会话管理，不可用时自动降级"""

import json
import hashlib
import time
import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


# ── 生命周期 ──────────────────────────────────────────────────

async def init_redis(url: str) -> aioredis.Redis | None:
    global _redis
    try:
        _redis = aioredis.from_url(url, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connected: %s", url)
        return _redis
    except Exception as e:
        logger.warning("Redis unavailable, degrading gracefully: %s", e)
        _redis = None
        return None


def get_redis() -> aioredis.Redis | None:
    return _redis


async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


# ── 通用缓存 ─────────────────────────────────────────────────

async def cache_get(key: str):
    """从 Redis 获取 JSON 值，未命中或出错返回 None"""
    r = get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def cache_set(key: str, value, ttl: int = 3600):
    """写入 JSON 值到 Redis，带 TTL。Redis 不可用时静默跳过"""
    r = get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception:
        pass


async def cache_delete(key: str):
    r = get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception:
        pass


def make_symptom_key(symptoms: list[str], prefix: str = "diag") -> str:
    """根据排序后的症状列表生成确定性缓存 key"""
    sorted_s = "|".join(sorted(s.strip().lower() for s in symptoms if s.strip()))
    h = hashlib.sha256(sorted_s.encode()).hexdigest()[:16]
    return f"mc:{prefix}:{h}"


# ── 滑动窗口限流 ──────────────────────────────────────────────

from collections import defaultdict
import asyncio

_mem_rate_limit: dict[str, list[float]] = defaultdict(list)
_mem_lock = asyncio.Lock()


async def check_rate_limit_memory(key: str, limit: int, window: int = 60) -> bool:
    """内存滑动窗口限流，用作 Redis 故障时的降级兜底"""
    async with _mem_lock:
        now = time.time()
        cutoff = now - window
        timestamps = _mem_rate_limit[key]
        valid_ts = [ts for ts in timestamps if ts > cutoff]
        _mem_rate_limit[key] = valid_ts
        if len(valid_ts) >= limit:
            return False
        valid_ts.append(now)
        return True


async def check_rate_limit(key: str, limit: int, window: int = 60) -> bool:
    """滑动窗口限流。返回 True 表示允许，False 表示超限。Redis 不可用时降级为内存限流"""
    r = get_redis()
    if r is None:
        logger.warning("Redis 客户端未连接，降级为内存限流")
        return await check_rate_limit_memory(key, limit, window)
    try:
        now = time.time()
        member = f"{now}:{id(object())}"
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        pipe.zadd(key, {member: now})
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[1]
        return count < limit
    except Exception as e:
        logger.warning("Redis 限流操作失败，降级为内存限流: %s", e)
        return await check_rate_limit_memory(key, limit, window)


# ── 会话状态缓存 ──────────────────────────────────────────────

async def cache_session_state(session_id: str, state: dict, ttl: int = 300):
    key = f"mc:sess:{session_id}"
    await cache_set(key, state, ttl=ttl)


async def get_cached_session_state(session_id: str) -> dict | None:
    key = f"mc:sess:{session_id}"
    return await cache_get(key)


async def invalidate_session_cache(session_id: str):
    key = f"mc:sess:{session_id}"
    await cache_delete(key)


# ── 活跃会话追踪 ──────────────────────────────────────────────

async def track_session(session_id: str, ttl: int = 1800):
    r = get_redis()
    if r is None:
        return
    try:
        await r.set(f"mc:active:{session_id}", "1", ex=ttl)
        await r.sadd("mc:active_sessions", session_id)
    except Exception:
        pass


async def untrack_session(session_id: str):
    r = get_redis()
    if r is None:
        return
    try:
        await r.delete(f"mc:active:{session_id}")
        await r.srem("mc:active_sessions", session_id)
    except Exception:
        pass


async def get_active_session_count() -> int:
    r = get_redis()
    if r is None:
        return -1
    try:
        return await r.scard("mc:active_sessions")
    except Exception:
        return -1
