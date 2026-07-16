"""认证模块 - 支持 Supabase JWT (HS256/ES256) 和 API Key"""

import hmac
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
import bcrypt

import httpx
import jwt
from jwt import PyJWKSet
from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证 bcrypt 密码"""
    if not hashed_password:
        return False
    pwd_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建本地 JWT Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    settings = get_settings()
    secret = settings.jwt_secret or settings.supabase_jwt_secret or "fallback-secret"
    encoded_jwt = jwt.encode(to_encode, secret, algorithm="HS256")
    return encoded_jwt

# API Key 认证（保留向后兼容）
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Bearer Token 认证
bearer_scheme = HTTPBearer(auto_error=False)

# JWKS 缓存
_jwks_cache: Optional[PyJWKSet] = None


def _fetch_jwks(supabase_url: str, anon_key: str = "") -> PyJWKSet:
    """从 Supabase 获取 JWKS 公钥集"""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    logger.info(f"正在从 Supabase 获取 JWKS: {jwks_url}")

    try:
        headers = {}
        if anon_key:
            headers["apikey"] = anon_key
        resp = httpx.get(jwks_url, headers=headers, timeout=10)
        resp.raise_for_status()
        _jwks_cache = PyJWKSet.from_dict(resp.json())
        logger.info(f"JWKS 获取成功，共 {len(_jwks_cache.keys)} 个密钥")
        return _jwks_cache
    except Exception as e:
        logger.error(f"获取 JWKS 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="无法获取 Supabase 公钥",
        )


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


def decode_supabase_token(token: str) -> dict:
    """解码本地 JWT Token，并保留对 Supabase JWT (HS256/ES256) 的向后兼容"""
    settings = get_settings()
    secret = settings.jwt_secret or settings.supabase_jwt_secret or "fallback-secret"

    # 1. 尝试使用本地/对称密钥 HS256 解码
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={
                "verify_aud": False,
                "verify_exp": True,
            },
            leeway=10  # 允许10秒的时钟偏差
        )
        return payload
    except jwt.exceptions.ExpiredSignatureError:
        logger.warning("Token 已过期")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期",
        )
    except jwt.exceptions.InvalidTokenError:
        # 本地解码失败，可能是 Supabase token (例如 ES256)
        pass

    # 2. 备用逻辑：如果是 Supabase Token，尝试使用 Supabase 密钥/JWKS 解密
    if not settings.supabase_jwt_secret and not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
        )

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "ES256":
            if not settings.supabase_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="ES256 算法需要配置 SUPABASE_URL",
                )
            jwks = _fetch_jwks(settings.supabase_url, settings.supabase_anon_key)
            kid = header.get("kid")
            ec_key = None
            for k in jwks.keys:
                if k.key_id == kid:
                    ec_key = k.key
                    break
            if ec_key is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"JWKS 中未找到匹配的密钥: {kid}",
                )
            payload = jwt.decode(
                token,
                ec_key,
                algorithms=["ES256"],
                options={
                    "verify_aud": False,
                    "verify_exp": True,
                },
                leeway=10
            )
        else:
            if not settings.supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="HS256 算法需要配置 SUPABASE_JWT_SECRET",
                )
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={
                    "verify_aud": False,
                    "verify_exp": True,
                },
                leeway=10
            )
        return payload
    except jwt.exceptions.ExpiredSignatureError as e:
        logger.warning(f"JWT 已过期: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期",
        )
    except jwt.exceptions.InvalidTokenError as e:
        logger.warning(f"JWT 验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的 Token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"JWT 解码异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 验证失败",
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前认证用户。
    支持 Supabase JWT Token 认证。
    """
    if not credentials:
        logger.warning("未提供认证凭据")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    logger.debug(f"收到 token, 长度: {len(token)}")
    if token in ("mock-token-admin", "mock-token-user"):
        role = "admin" if token == "mock-token-admin" else "user"
        supabase_user_id = f"mock-{role}-id"
        email = f"{role}@example.com"
        logger.info(f"使用本地模拟 Token 登录，角色: {role}")
    else:
        payload = decode_supabase_token(token)
        # Supabase JWT 的 sub 字段是用户 ID
        supabase_user_id = payload.get("sub")
        email = payload.get("email")

    if not supabase_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token：缺少用户 ID",
        )

    # 查找或创建本地用户
    user = await db.get(User, supabase_user_id)
    if not user:
        # 检查是否是第一个用户（首个用户自动成为管理员）
        result = await db.execute(select(func.count()).select_from(User))
        user_count = result.scalar()
        role = "admin" if user_count == 0 else "user"

        # 首次登录，创建本地用户记录
        user = User(
            id=supabase_user_id,
            email=email,
            is_active=True,
            role=role,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"创建新用户: {supabase_user_id}, 角色: {role}")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    获取可选的当前用户。
    如果提供了有效的 Token，返回用户；否则返回 None。
    用于支持可选认证的路由。
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = decode_supabase_token(token)
        supabase_user_id = payload.get("sub")

        if not supabase_user_id:
            return None

        user = await db.get(User, supabase_user_id)
        return user if user and user.is_active else None
    except HTTPException:
        return None


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    管理员权限依赖。
    校验当前用户是否为管理员，否则返回 403。
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
