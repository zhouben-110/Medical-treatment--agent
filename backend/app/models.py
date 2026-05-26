from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


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
