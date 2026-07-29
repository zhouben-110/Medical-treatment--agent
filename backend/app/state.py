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
    # ── M3: 患者属性与用药红线 ──
    patient_profile: dict  # 格式: {"age_group": str|None, "is_pregnant": bool|None, "allergies": list[str]}
    # ── M4: 诊断 Agent 自主工具循环 ──
    # scratchpad 是 Agent 内部推理轨迹（含 tool_calls / tool 结果），
    # 与用户可见的 messages 严格隔离，由 finalize 节点负责清空。
    diagnose_scratchpad: Annotated[List, add_messages]
    tool_trace: List[dict]  # 审计留痕: [{"tool": str, "args": dict, "returned": str}]
    tool_iterations: int
    diagnose_started_at: float  # 墙钟预算起点 (time.monotonic)
    agent_llm_failed: bool      # Agent LLM 调用失败标记，供路由收口
