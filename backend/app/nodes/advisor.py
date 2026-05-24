from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.config import get_settings

settings = get_settings()
llm = ChatOpenAI(
    api_key=settings.llm_api_key,
    model=settings.llm_model,
    base_url=settings.llm_base_url,
    temperature=0.3
)

ADVICE_PROMPT = """你是一个医疗AI助手。根据诊断结果，生成治疗建议。

可能的疾病: {diseases}
症状: {symptoms}
置信度: {confidence}

请生成:
1. 治疗建议（包括用药建议、生活调理）
2. 注意事项
3. 是否需要就医

重要：在回复末尾必须加上免责声明："以上内容仅供参考，不构成医疗建议。如有不适，请及时就医。"

返回完整的建议内容。"""


async def generate_advice(state: MedicalAgentState) -> dict:
    """生成治疗建议"""
    prompt = ChatPromptTemplate.from_template(ADVICE_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "diseases": ", ".join(state.get("possible_diseases", [])),
        "symptoms": ", ".join(state.get("symptoms", [])),
        "confidence": f"{state.get('confidence', 0) * 100:.0f}%"
    })

    return {
        "messages": [{"role": "assistant", "content": response.content}],
        "treatment_plan": response.content,
        "current_stage": "completed"
    }


async def generate_advice_stream(diseases: list, symptoms: list, confidence: float):
    """流式生成治疗建议"""
    prompt = ChatPromptTemplate.from_template(ADVICE_PROMPT)
    chain = prompt | llm

    async for chunk in chain.astream({
        "diseases": ", ".join(diseases),
        "symptoms": ", ".join(symptoms),
        "confidence": f"{confidence * 100:.0f}%"
    }):
        if chunk.content:
            yield chunk.content
