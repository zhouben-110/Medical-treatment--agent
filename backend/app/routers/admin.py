"""管理员路由 - 用户管理"""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.auth import require_admin
from app.database import get_db

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


class UserUpdateRole(BaseModel):
    role: str  # 'user' or 'admin'


class UserUpdateStatus(BaseModel):
    is_active: bool


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取用户列表（分页）"""
    offset = (page - 1) * size

    # 总数
    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar()

    # 分页查询
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(size)
    )
    users = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in users
        ],
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserUpdateRole,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """修改用户角色"""
    if body.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色只能是 'user' 或 'admin'",
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不能修改自己的角色
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色",
        )

    user.role = body.role
    await db.commit()

    return {"id": user.id, "email": user.email, "role": user.role}


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    body: UserUpdateStatus,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不能禁用自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用自己",
        )

    user.is_active = body.is_active
    await db.commit()

    return {"id": user.id, "email": user.email, "is_active": user.is_active}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除用户及其所有会话数据"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    await db.delete(user)
    await db.commit()

    return {"id": user_id, "detail": "用户已删除"}
