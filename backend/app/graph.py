from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.config import get_settings
from app.nodes import analyze_symptoms, generate_question
from app.nodes.diagnose_and_advise import diagnose_and_advise
from app.nodes.diagnose_agent import (
    diagnose_agent, tool_executor_node, finalize_diagnosis, route_after_agent,
)
from app.nodes.triage import run_triage, _check_red_flags, EMERGENCY_RESPONSE
from app.llm import get_llm

MAX_USER_TURNS = 5


def _count_user_turns(messages) -> int:
    count = 0
    for m in messages or []:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
        if role in ("human", "user"):
            count += 1
    return count


# ── Supervisor：LLM 路由决策节点 ──────────────────────────────

SUPERVISOR_PROMPT = """你是一个医疗多 Agent 系统的调度器。根据当前状态决定下一步调用哪个 Agent。

当前阶段: {current_stage}
已识别症状: {symptoms}
是否紧急: {is_emergency}
是否需要更多信息: {need_more_info}
用户对话轮次: {user_turns}/{max_turns}

路由规则（严格遵守）:
1. 如果 current_stage 为 "start" → 调用 triage（分诊）
2. 如果 current_stage 为 "triaged" → 调用 analyze（症状分析）
3. 如果 current_stage 为 "analyzing" 且 need_more_info 为 true 且轮次未满 → 调用 question（追问）
4. 如果 current_stage 为 "analyzing" 且 (need_more_info 为 false 或轮次已满) → 调用 diagnose（诊断+建议）
5. 如果 current_stage 为 "questioning" → 调用 diagnose（诊断+建议）
6. 如果 current_stage 为 "completed" 或 "emergency" → 结束

只回复一个 Agent 名称: triage, analyze, question, diagnose, 或 finish"""

VALID_ROUTES = {"triage", "analyze", "question", "diagnose", "finish"}


async def supervisor_node(state: MedicalAgentState) -> dict:
    """Supervisor 节点：决定路由目标（优先确定性路由，仅 analyzing 阶段用 LLM）"""
    stage = state.get("current_stage", "start")

    # 红旗快速通道
    if stage == "start":
        last_user = ""
        for m in reversed(state.get("messages", []) or []):
            role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
            if role in ("human", "user"):
                last_user = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
                break
        if _check_red_flags(last_user):
            return {"current_stage": "emergency", "is_emergency": True,
                    "emergency_message": EMERGENCY_RESPONSE,
                    "messages": [{"role": "assistant", "content": EMERGENCY_RESPONSE}]}

    # 确定性路由：大部分阶段不需要 LLM
    if stage in ("start", "triaged", "questioning"):
        route = _deterministic_route(state)
        return {"current_stage": f"supervisor:{route}"}

    if stage == "analyzing":
        # 仅在 analyzing 阶段需要 LLM 判断是否追问
        llm = get_llm(temperature=0)
        prompt = ChatPromptTemplate.from_template(SUPERVISOR_PROMPT)
        chain = prompt | llm
        response = await chain.ainvoke({
            "current_stage": stage,
            "symptoms": ", ".join(state.get("symptoms", [])) or "（无）",
            "is_emergency": "是" if state.get("is_emergency") else "否",
            "need_more_info": "是" if state.get("need_more_info", True) else "否",
            "user_turns": _count_user_turns(state.get("messages", [])),
            "max_turns": MAX_USER_TURNS,
        })
        route = response.content.strip().lower()
        if route not in VALID_ROUTES:
            route = _deterministic_route(state)
        return {"current_stage": f"supervisor:{route}"}

    # 其他阶段用确定性路由
    route = _deterministic_route(state)
    return {"current_stage": f"supervisor:{route}"}


def _deterministic_route(state: MedicalAgentState) -> str:
    """确定性兜底路由（不依赖 LLM）"""
    stage = state.get("current_stage", "start")

    if stage == "start":
        return "triage"
    if stage == "triaged":
        return "analyze"
    if stage.startswith("supervisor:"):
        stage = stage.split(":", 1)[1]
        if stage in VALID_ROUTES:
            return stage

    if stage == "analyzing":
        user_turns = _count_user_turns(state.get("messages", []))
        if state.get("need_more_info", True) and user_turns < MAX_USER_TURNS:
            return "question"
        return "diagnose"
    if stage == "questioning":
        return "diagnose"
    if stage == "diagnosing":
        return "diagnose"
    return "finish"


def route_after_triage(state: MedicalAgentState) -> str:
    """急诊 → END, 非急诊 → 回 supervisor 继续流程"""
    if state.get("is_emergency") or state.get("current_stage") == "emergency":
        return "emergency"
    return "continue"


def route_after_supervisor(state: MedicalAgentState) -> str:
    """根据 supervisor 决策路由到对应 Agent"""
    stage = state.get("current_stage", "start")

    # 从 supervisor:xxx 中提取目标
    if stage.startswith("supervisor:"):
        target = stage.split(":", 1)[1]
        if target == "finish":
            return "finish"
        if target in VALID_ROUTES:
            # diagnose 分支按 flag 选固定管线或 Agent
            if target == "diagnose" and get_settings().enable_agent_diagnose:
                return "diagnose_agent"
            return target

    # 兜底：确定性路由
    route = _deterministic_route(state)
    if route == "diagnose" and get_settings().enable_agent_diagnose:
        return "diagnose_agent"
    return "finish" if route == "finish" else route


# ── Graph 构建 ────────────────────────────────────────────────

def build_graph() -> StateGraph:
    workflow = StateGraph(MedicalAgentState)

    # 注册所有节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("triage", run_triage)
    workflow.add_node("analyze", analyze_symptoms)
    workflow.add_node("question", generate_question)
    workflow.add_node("diagnose", diagnose_and_advise)
    # 自主诊断 Agent 子图：diagnose_agent ↔ tools → finalize
    workflow.add_node("diagnose_agent", diagnose_agent)
    workflow.add_node("tools", tool_executor_node)
    workflow.add_node("finalize", finalize_diagnosis)

    # 入口 → supervisor
    workflow.set_entry_point("supervisor")

    # supervisor → 路由到各 Agent
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "triage": "triage",
            "analyze": "analyze",
            "question": "question",
            "diagnose": "diagnose",
            "diagnose_agent": "diagnose_agent",
            "finish": END,
        },
    )

    # triage → 急诊 END / 非急诊回 supervisor
    workflow.add_conditional_edges(
        "triage",
        route_after_triage,
        {"emergency": END, "continue": "supervisor"},
    )
    workflow.add_edge("analyze", "supervisor")  # 分析完回 supervisor 决策
    workflow.add_edge("question", END)          # 追问直接结束（等下一轮用户输入）
    workflow.add_edge("diagnose", END)          # 诊断+建议完直接结束

    # 自主诊断 Agent 循环
    workflow.add_conditional_edges(
        "diagnose_agent",
        route_after_agent,
        {"tools": "tools", "finalize": "finalize"},
    )
    workflow.add_edge("tools", "diagnose_agent")   # 工具结果回 Agent 决策
    workflow.add_edge("finalize", END)

    return workflow


# 由 main.py 的 lifespan 在注入 checkpointer 后赋值
medical_graph: CompiledStateGraph | None = None
