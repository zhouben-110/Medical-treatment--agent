from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from app.state import MedicalAgentState
from app.nodes import analyze_symptoms, generate_question, match_diseases, generate_advice

MAX_USER_TURNS = 5


def _count_user_turns(messages) -> int:
    count = 0
    for m in messages or []:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
        if role in ("human", "user"):
            count += 1
    return count


def route_after_analyze(state: MedicalAgentState) -> str:
    user_turns = _count_user_turns(state.get("messages", []))
    if state.get("need_more_info", True) and user_turns < MAX_USER_TURNS:
        return "question"
    return "diagnose"


def build_graph() -> StateGraph:
    workflow = StateGraph(MedicalAgentState)
    workflow.add_node("analyze", analyze_symptoms)
    workflow.add_node("question", generate_question)
    workflow.add_node("diagnose", match_diseases)
    workflow.add_node("advise", generate_advice)

    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {"question": "question", "diagnose": "diagnose"}
    )
    workflow.add_edge("question", END)
    workflow.add_edge("diagnose", "advise")
    workflow.add_edge("advise", END)
    return workflow


# 由 main.py 的 lifespan 在注入 checkpointer 后赋值
medical_graph: CompiledStateGraph | None = None
