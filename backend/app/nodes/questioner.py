from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.llm import get_llm

QUESTION_PROMPT = """你是一个医疗AI助手。根据已知症状，生成追问问题。

已知症状: {symptoms}
对话历史: {conversation_history}

请生成1-3个关键追问，帮助判断病情。重点关注:
1. 症状持续时间
2. 伴随症状
3. 既往病史
4. 过敏史

直接返回追问内容，不要有多余格式。"""


async def generate_question(state: MedicalAgentState) -> dict:
    """生成追问问题"""
    llm = get_llm(temperature=0.3)
    prompt = ChatPromptTemplate.from_template(QUESTION_PROMPT)
    chain = prompt | llm

    history_msgs = state.get("messages", [])[-5:]
    history_lines = []
    for m in history_msgs:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else "?")
        text = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines)

    response = await chain.ainvoke({
        "symptoms": ", ".join(state.get("symptoms", [])),
        "conversation_history": history
    })

    return {
        "messages": [{"role": "assistant", "content": response.content}],
        "current_stage": "questioning"
    }
