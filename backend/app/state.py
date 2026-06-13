from typing import List, TypedDict, Annotated
from langgraph.graph import add_messages
from datetime import datetime


class Message(TypedDict):
    role: str
    content: str
    timestamp: str


class MedicalAgentState(TypedDict):
    messages: Annotated[List[Message], add_messages]
    symptoms: List[str]
    current_stage: str
    confidence: float
    possible_diseases: List[str]
    treatment_plan: str
    need_more_info: bool
    session_id: str
    retrieved_context: str
    # ── M2: 分诊/急诊 ──
    is_emergency: bool
    red_flags: List[str]
    emergency_message: str
