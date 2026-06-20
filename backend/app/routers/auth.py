from fastapi import APIRouter, Depends
from app.models import User
from app.auth import get_current_user

router = APIRouter()


@router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
