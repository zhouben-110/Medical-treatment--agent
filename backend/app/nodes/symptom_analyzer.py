from typing import Literal
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from app.state import MedicalAgentState
from app.llm import get_llm


class SymptomExtraction(BaseModel):
    """症状提取结构化输出"""
    symptoms: list[str] = Field(description="从用户描述中识别的症状列表")
    severity: Literal["轻度", "中度", "重度"] = Field(description="症状整体严重程度")
    need_more_info: bool = Field(description="是否需要更多信息才能初步判断")


SYMPTOM_ANALYSIS_PROMPT = """你是一个医疗AI助手。请从用户的描述中提取症状信息。

用户描述: {user_message}

已识别的症状: {existing_symptoms}

请提取新识别的症状，评估严重程度，并判断是否需要更多信息。"""


def _extract_latest_user_message(messages) -> str:
    for m in reversed(messages or []):
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
        if role in ("human", "user"):
            return getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
    return ""


async def analyze_symptoms(state: MedicalAgentState) -> dict:
    """从用户消息中提取症状（Pydantic 结构化输出）"""
    user_message = _extract_latest_user_message(state.get("messages", []))

    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(SymptomExtraction)
    prompt = ChatPromptTemplate.from_template(SYMPTOM_ANALYSIS_PROMPT)
    chain = prompt | structured_llm

    try:
        result = await chain.ainvoke({
            "user_message": user_message,
            "existing_symptoms": ", ".join(state.get("symptoms", [])) or "（无）",
        })
        new_symptoms = result.symptoms
        need_more = result.need_more_info
    except Exception:
        # 结构化输出失败时保留已有状态
        return {"current_stage": "analyzing"}

    # 保持顺序去重
    all_symptoms = list(dict.fromkeys((state.get("symptoms") or []) + new_symptoms))

    return {
        "symptoms": all_symptoms,
        "need_more_info": need_more,
        "current_stage": "analyzing",
    }
