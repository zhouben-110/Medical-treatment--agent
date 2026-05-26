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


def _extract_latest_user_message(messages) -> str:
    for m in reversed(messages or []):
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
        if role in ("human", "user"):
            return getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
    return ""


def _grab_line(content: str, prefix: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix.lower()):
            return stripped.split(":", 1)[1].strip() if ":" in stripped else ""
    return None


async def analyze_symptoms(state: MedicalAgentState) -> dict:
    """从用户消息中提取症状"""
    user_message = _extract_latest_user_message(state.get("messages", []))

    prompt = ChatPromptTemplate.from_template(SYMPTOM_ANALYSIS_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "user_message": user_message,
        "existing_symptoms": ", ".join(state.get("symptoms", []))
    })
    content = response.content

    symptoms_str = _grab_line(content, "symptoms") or _grab_line(content, "症状")
    new_symptoms = [s.strip() for s in (symptoms_str or "").split(",") if s.strip()]

    need_more_str = _grab_line(content, "need_more_info")
    if need_more_str is None:
        need_more = state.get("need_more_info", True)
    else:
        need_more = "true" in need_more_str.lower()

    # 保持顺序去重
    all_symptoms = list(dict.fromkeys((state.get("symptoms") or []) + new_symptoms))

    return {
        "symptoms": all_symptoms,
        "need_more_info": need_more,
        "current_stage": "analyzing"
    }
