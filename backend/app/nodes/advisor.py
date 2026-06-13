from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.llm import get_llm

# 由 main.py lifespan 注入
retriever = None

ADVICE_PROMPT = """你是一个医疗AI助手。根据诊断结果和医学知识库，生成治疗建议。

可能的疾病: {diseases}
症状: {symptoms}
置信度: {confidence}

医学知识参考:
{medical_context}

请基于以上医学知识参考，生成:
1. 治疗建议（包括用药建议、生活调理）
2. 注意事项
3. 是否需要就医

重要：在回复末尾必须加上免责声明："以上内容仅供参考，不构成医疗建议。如有不适，请及时就医。"

返回完整的建议内容。"""


async def generate_advice(state: MedicalAgentState) -> dict:
    """生成治疗建议"""
    diseases = state.get("possible_diseases", [])
    symptoms = state.get("symptoms", [])

    # RAG 检索
    medical_context = ""
    if retriever:
        try:
            medical_context = await retriever.retrieve_for_advice(diseases, symptoms)
        except Exception as e:
            print(f"RAG retrieval error in advise: {e}")

    llm = get_llm(temperature=0.3)
    prompt = ChatPromptTemplate.from_template(ADVICE_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "diseases": ", ".join(diseases),
        "symptoms": ", ".join(symptoms),
        "confidence": f"{state.get('confidence', 0) * 100:.0f}%",
        "medical_context": medical_context or "（无相关知识库数据）",
    })

    return {
        "messages": [{"role": "assistant", "content": response.content}],
        "treatment_plan": response.content,
        "current_stage": "completed",
    }
