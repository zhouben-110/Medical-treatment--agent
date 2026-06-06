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
