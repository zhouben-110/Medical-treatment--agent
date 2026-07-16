from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import User
from app.database import get_db
from app.auth import get_current_user, hash_password, verify_password, create_access_token
from app.schemas import UserRegister, UserLogin, TokenResponse, UserResponse, ChangePasswordRequest

router = APIRouter()


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查邮箱是否已被注册
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )

    # 检查是否是第一个用户，首个用户自动设定为 admin 角色
    count_result = await db.execute(select(func.count()).select_from(User))
    user_count = count_result.scalar()
    role = "admin" if user_count == 0 else "user"

    # 创建新用户
    hashed_pwd = hash_password(data.password)
    new_user = User(
        email=data.email,
        hashed_password=hashed_pwd,
        is_active=True,
        role=role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {"message": "注册成功"}


@router.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录并签发 JWT"""
    # 查询用户
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    # 签发 JWT
    access_token = create_access_token(data={"sub": user.id, "email": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/auth/change-password")
async def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    hashed_pwd = hash_password(data.password)
    user.hashed_password = hashed_pwd
    await db.commit()
    return {"message": "密码修改成功"}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return user
