from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: Optional[UUID] = Field(None, description="会话ID")


class ChatResponse(BaseModel):
    reply: str
    stage: str
    symptoms: List[str]
    session_id: str
    need_more_info: bool = False
    possible_diseases: List[str] = []


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: datetime


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    message_count: int


class SessionDetailResponse(BaseModel):
    messages: List[MessageResponse]
    diagnosis: Optional[str]


class SymptomCategoryResponse(BaseModel):
    name: str
    symptoms: List[str]


class SymptomListResponse(BaseModel):
    categories: List[SymptomCategoryResponse]


class UserRegister(BaseModel):
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, description="密码")


class UserLogin(BaseModel):
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, description="密码")


class ChangePasswordRequest(BaseModel):
    password: str = Field(..., min_length=6, description="新密码")


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
