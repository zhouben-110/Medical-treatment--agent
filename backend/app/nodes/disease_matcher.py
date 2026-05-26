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

# 由 main.py lifespan 注入
retriever = None

DISEASE_MATCH_PROMPT = """你是一个医疗AI助手。根据症状组合和医学知识库，匹配可能的疾病。

症状列表: {symptoms}
对话历史: {conversation_history}

医学知识参考:
{medical_context}

请基于以上医学知识参考，返回:
1. 可能的疾病列表（最多3个，按可能性排序）
2. 每个疾病的置信度（0-100）
3. 简要说明判断依据

返回格式（严格遵守）:
disease1: 疾病名 (置信度%)
disease2: 疾病名 (置信度%)
disease3: 疾病名 (置信度%)
reason: 判断依据"""


async def match_diseases(state: MedicalAgentState) -> dict:
    """匹配可能的疾病"""
    import re

    symptoms = state.get("symptoms", [])

    # RAG 检索
    medical_context = ""
    if retriever:
        try:
            medical_context = await retriever.retrieve_for_diagnosis(symptoms)
        except Exception as e:
            print(f"RAG retrieval error in diagnose: {e}")

    prompt = ChatPromptTemplate.from_template(DISEASE_MATCH_PROMPT)
    chain = prompt | llm

    history_msgs = state.get("messages", [])[-5:]
    history_lines = []
    for m in history_msgs:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else "?")
        text = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines)

    response = await chain.ainvoke({
        "symptoms": ", ".join(symptoms),
        "conversation_history": history,
        "medical_context": medical_context or "（无相关知识库数据）",
    })

    content = response.content
    diseases = []
    confidence = 0.5

    for line in content.split("\n"):
        if line.startswith("disease"):
            parts = line.split(":", 1)
            if len(parts) < 2:
                continue
            rest = parts[1].strip()
            match = re.match(r'(.+?)\s*\((\d+)%?\)', rest)
            if match:
                disease_name = match.group(1).strip()
                try:
                    confidence = int(match.group(2)) / 100
                except ValueError:
                    confidence = 0.5
            else:
                disease_name = rest.split("(")[0].strip()
            if disease_name:
                diseases.append(disease_name)

    return {
        "possible_diseases": diseases,
        "confidence": confidence,
        "current_stage": "diagnosing",
        "retrieved_context": medical_context,
    }
