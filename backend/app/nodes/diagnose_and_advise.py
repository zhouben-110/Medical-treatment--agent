"""Combined diagnosis + advice node: single LLM call for streaming advice."""

from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.llm import get_llm

# 由 main.py lifespan 注入
retriever = None


ADVICE_PROMPT = """你是一个医疗AI助手。根据症状和医学知识库，给出诊断建议。

症状: {symptoms}
对话: {conversation_history}
参考: {medical_context}

请回答:
1. 可能的疾病及依据
2. 治疗建议（用药、调理）
3. 注意事项及是否需就医
4. 末尾加免责声明"""


async def diagnose_and_advise(state: MedicalAgentState) -> dict:
    """诊断 + 建议：获取完整上下文后单次 LLM 调用"""
    symptoms = state.get("symptoms", [])

    # 第一步：MCP 诊断检索（疾病匹配 + 文献）
    diagnosis_context = ""
    disease_names = []
    if retriever:
        try:
            diagnosis_context, disease_names = await retriever.retrieve_for_diagnosis(symptoms)
        except Exception as e:
            print(f"RAG retrieval error: {e}")

    # 第二步：MCP 疾病详情检索（治疗方案、就医指征等）
    detail_context = ""
    if retriever and disease_names:
        try:
            detail_context = await retriever.retrieve_for_advice(disease_names, symptoms)
        except Exception as e:
            print(f"RAG retrieval error for details: {e}")

    # 合并上下文
    full_context = diagnosis_context
    if detail_context:
        full_context = full_context + "\n\n" + detail_context if full_context else detail_context

    # 对话历史
    history_msgs = state.get("messages", [])[-5:]
    history_lines = []
    for m in history_msgs:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else "?")
        text = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines)

    # LLM 生成建议（流式输出到前端）
    llm = get_llm(temperature=0.3)
    chain = ChatPromptTemplate.from_template(ADVICE_PROMPT) | llm
    response = await chain.ainvoke({
        "symptoms": ", ".join(symptoms),
        "conversation_history": history,
        "medical_context": full_context or "（无相关知识库数据）",
    })
    advice = response.content

    return {
        "possible_diseases": disease_names,
        "confidence": 0.7 if disease_names else 0.5,
        "treatment_plan": advice,
        "current_stage": "completed",
        "retrieved_context": full_context,
        "messages": [{"role": "assistant", "content": advice}],
    }
