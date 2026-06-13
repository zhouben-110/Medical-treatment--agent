import logging
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List
from app.state import MedicalAgentState
from app.llm import get_llm
from app.cache import get_cached_diagnosis, cache_diagnosis

logger = logging.getLogger(__name__)

# 由 main.py lifespan 注入
retriever = None


class DiseaseResult(BaseModel):
    name: str = Field(description="疾病名称")
    confidence: int = Field(description="置信度 0-100")


class DiseaseDiagnosis(BaseModel):
    diseases: List[DiseaseResult] = Field(description="可能的疾病列表，最多3个")
    reason: str = Field(description="判断依据")


DISEASE_MATCH_PROMPT = """你是一个医疗AI助手。根据症状组合和医学知识库，匹配可能的疾病。

症状列表: {symptoms}
对话历史: {conversation_history}

医学知识参考:
{medical_context}

请分析症状并返回可能的疾病列表，最多3个，按可能性排序，confidence 为 0-100 的整数。"""


async def match_diseases(state: MedicalAgentState) -> dict:
    """匹配可能的疾病"""
    symptoms = state.get("symptoms", [])

    # 检查缓存
    cached = get_cached_diagnosis(symptoms)
    if cached:
        return cached

    # RAG 检索
    medical_context = ""
    if retriever:
        try:
            medical_context = await retriever.retrieve_for_diagnosis(symptoms)
        except Exception as e:
            logger.warning("RAG retrieval error in diagnose: %s", e)

    llm = get_llm(temperature=0)
    prompt = ChatPromptTemplate.from_template(DISEASE_MATCH_PROMPT)
    chain = prompt | llm.with_structured_output(DiseaseDiagnosis)

    history_msgs = state.get("messages", [])[-5:]
    history_lines = []
    for m in history_msgs:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else "?")
        text = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines)

    try:
        parsed: DiseaseDiagnosis = await chain.ainvoke({
            "symptoms": ", ".join(symptoms),
            "conversation_history": history,
            "medical_context": medical_context or "（无相关知识库数据）",
        })
        diseases = [d.name for d in parsed.diseases]
        confidence = parsed.diseases[0].confidence / 100 if parsed.diseases else 0.5
    except Exception as e:
        logger.warning("structured output failed, falling back to plain LLM: %s", e)
        # fallback: 不用 structured output，手动解析
        plain_chain = ChatPromptTemplate.from_template(
            DISEASE_MATCH_PROMPT + "\n\n请返回 JSON 格式: {{\"diseases\": [{{\"name\": \"疾病名\", \"confidence\": 70}}], \"reason\": \"判断依据\"}}"
        ) | get_llm(temperature=0)
        response = await plain_chain.ainvoke({
            "symptoms": ", ".join(symptoms),
            "conversation_history": history,
            "medical_context": medical_context or "（无相关知识库数据）",
        })
        try:
            import json, re
            json_str = response.content
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            parsed = DiseaseDiagnosis.model_validate_json(json_str.strip())
            diseases = [d.name for d in parsed.diseases]
            confidence = parsed.diseases[0].confidence / 100 if parsed.diseases else 0.5
        except Exception:
            logger.warning("fallback JSON parsing also failed")
            diseases = []
            confidence = 0.5

    result = {
        "possible_diseases": diseases,
        "confidence": confidence,
        "current_stage": "diagnosing",
        "retrieved_context": medical_context,
    }
    cache_diagnosis(symptoms, result)
    return result
