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
    user_message: str
