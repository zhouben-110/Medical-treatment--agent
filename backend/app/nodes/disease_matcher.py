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

DISEASE_MATCH_PROMPT = """你是一个医疗AI助手。根据症状组合，匹配可能的疾病。

症状列表: {symptoms}
对话历史: {conversation_history}

请返回:
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

    prompt = ChatPromptTemplate.from_template(DISEASE_MATCH_PROMPT)
    chain = prompt | llm

    history = "\n".join([f"{m.type}: {m.content}" for m in state.get("messages", [])[-5:]])

    response = await chain.ainvoke({
        "symptoms": ", ".join(state.get("symptoms", [])),
        "conversation_history": history
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
            # 提取疾病名称和置信度
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
        "current_stage": "diagnosing"
    }
