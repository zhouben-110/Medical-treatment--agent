from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.config import get_settings

settings = get_settings()
llm = ChatOpenAI(
    api_key=settings.llm_api_key,
    model=settings.llm_model,
    base_url=settings.llm_base_url,
    temperature=0
)

SYMPTOM_ANALYSIS_PROMPT = """你是一个医疗AI助手。请从用户的描述中提取症状信息。

用户描述: {user_message}

已识别的症状: {existing_symptoms}

请返回:
1. 新识别的症状列表（用逗号分隔）
2. 症状的严重程度（轻度/中度/重度）
3. 是否需要更多信息才能初步判断

返回格式（严格遵守）:
symptoms: 症状1, 症状2, ...
severity: 轻度/中度/重度
need_more_info: true/false"""


async def analyze_symptoms(state: MedicalAgentState) -> dict:
    """从用户消息中提取症状"""
    prompt = ChatPromptTemplate.from_template(SYMPTOM_ANALYSIS_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "user_message": state["user_message"],
        "existing_symptoms": ", ".join(state.get("symptoms", []))
    })

    content = response.content
    # 解析响应
    symptoms_line = [line for line in content.split("\n") if line.startswith("symptoms:")][0]
    new_symptoms = [s.strip() for s in symptoms_line.replace("symptoms:", "").split(",") if s.strip()]

    need_more_line = [line for line in content.split("\n") if line.startswith("need_more_info:")][0]
    need_more = "true" in need_more_line.lower()

    # 合并症状
    all_symptoms = list(set(state.get("symptoms", []) + new_symptoms))

    return {
        "symptoms": all_symptoms,
        "need_more_info": need_more,
        "current_stage": "analyzing"
    }
