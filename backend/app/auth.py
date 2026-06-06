"""API Key 认证中间件"""

import hmac
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """验证 API Key。如果未配置 API_KEY 则跳过验证（开发模式）。"""
    settings = get_settings()

    # 未配置 API_KEY 时跳过验证（仅限开发环境）
    if not settings.api_key:
        return True

    if not api_key or not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
        )
    return True
