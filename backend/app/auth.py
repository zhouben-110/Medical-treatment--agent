"""API Key 认证中间件"""

import hmac
import logging

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """验证 API Key。未配置 API_KEY 时拒绝所有请求。"""
    settings = get_settings()

    # 未配置 API_KEY 时拒绝请求，防止生产环境裸奔
    if not settings.api_key:
        logger.error("API_KEY 未配置，拒绝所有请求。请在 .env 中设置 API_KEY。")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务未正确配置：缺少 API_KEY",
        )

    if not api_key or not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
        )
    return True
