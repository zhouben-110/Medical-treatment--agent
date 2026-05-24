from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import analyze_symptoms, generate_question, match_diseases, generate_advice


def should_continue(state: MedicalAgentState) -> str:
    """判断是否需要继续追问"""
    if state.get("need_more_info", True) and len(state.get("messages", [])) < 10:
        return "question"
    return "diagnose"


def create_medical_graph():
    """创建医疗诊断状态机"""
    workflow = StateGraph(MedicalAgentState)

    # 添加节点
    workflow.add_node("analyze", analyze_symptoms)
    workflow.add_node("question", generate_question)
    workflow.add_node("diagnose", match_diseases)
    workflow.add_node("advise", generate_advice)

    # 设置入口
    workflow.set_entry_point("analyze")

    # 添加边
    workflow.add_conditional_edges(
        "analyze",
        should_continue,
        {
            "question": "question",
            "diagnose": "diagnose"
        }
    )
    workflow.add_edge("question", "analyze")
    workflow.add_edge("diagnose", "advise")
    workflow.add_edge("advise", END)

    return workflow.compile()


# 全局图实例
medical_graph = create_medical_graph()
