"""分诊/急诊 Agent：红旗症状 → 确定性急救短路"""

from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.llm import get_llm

# ── 红旗关键词：命中任意一个即短路到急救 ──────────────────────
RED_FLAG_KEYWORDS: list[str] = [
    # 心血管
    "胸痛", "胸闷痛", "心绞痛", "心肌梗死", "心脏骤停", "濒死感",
    # 呼吸
    "呼吸困难", "喘不过气", "窒息", "无法呼吸", "嘴唇发紫",
    # 神经
    "突然剧烈头痛", "意识丧失", "昏迷", "抽搐", "口齿不清",
    "一侧肢体无力", "嘴角歪斜", "视物模糊", "意识模糊",
    # 出血
    "大出血", "呕血", "咯血", "便血不止",
    # 过敏
    "过敏性休克", "喉头水肿", "全身过敏",
    # 其他
    "高热不退", "体温40", "体温41", "剧烈腹痛", "腹部板样强直",
]

EMERGENCY_RESPONSE = (
    "⚠️ 根据您描述的症状，可能存在紧急医疗风险。\n\n"
    "请立即拨打 **120 急救电话** 或前往最近的急诊科就诊。\n\n"
    "在等待急救期间：\n"
    "1. 保持冷静，尽量平躺或采取舒适体位\n"
    "2. 不要自行服药\n"
    "3. 如有随行人员，请告知他们您的症状\n\n"
    "以上内容仅供参考，不构成医疗建议。如有不适，请及时就医。"
)


class TriageResult(BaseModel):
    """分诊结构化输出"""
    is_emergency: bool = Field(description="是否为紧急情况")
    red_flags: list[str] = Field(default_factory=list, description="检测到的红旗症状")
    action: Literal["emergency_short_circuit", "continue_normal_flow"] = Field(
        description="处置建议"
    )
    reason: str = Field(description="判断理由")


def _check_red_flags(user_message: str) -> list[str]:
    """确定性红旗关键词匹配（零延迟，不调用 LLM）"""
    return [kw for kw in RED_FLAG_KEYWORDS if kw in user_message]


def _extract_latest_user_message(messages) -> str:
    for m in reversed(messages or []):
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
        if role in ("human", "user"):
            return getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
    return ""


TRIAGE_PROMPT = """你是一个医疗分诊专家。根据用户描述判断是否为紧急情况。

用户描述: {user_message}
已识别症状: {symptoms}

请判断:
1. 是否存在需要立即就医的紧急情况（如心梗、中风、严重过敏、大出血等）
2. 列出检测到的红旗症状
3. 给出处置建议"""


async def run_triage(state: MedicalAgentState) -> dict:
    """分诊节点：先做确定性红旗检查，不确定时再调 LLM"""
    user_message = _extract_latest_user_message(state.get("messages", []))

    # Layer 1: 确定性红旗关键词匹配
    red_flags = _check_red_flags(user_message)
    if red_flags:
        return {
            "is_emergency": True,
            "red_flags": red_flags,
            "emergency_message": EMERGENCY_RESPONSE,
            "current_stage": "emergency",
            "messages": [{"role": "assistant", "content": EMERGENCY_RESPONSE}],
        }

    # Layer 2: LLM 结构化输出分诊（处理关键词未覆盖的模糊情况）
    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(TriageResult)
    prompt = ChatPromptTemplate.from_template(TRIAGE_PROMPT)
    chain = prompt | structured_llm

    try:
        result = await chain.ainvoke({
            "user_message": user_message,
            "symptoms": ", ".join(state.get("symptoms", [])) or "（尚未提取）",
        })
    except Exception:
        # LLM 分诊失败时默认非紧急，不阻塞主流程
        return {"is_emergency": False, "current_stage": "triaged"}

    if result.is_emergency:
        flags = result.red_flags or ["LLM识别的紧急情况"]
        return {
            "is_emergency": True,
            "red_flags": flags,
            "emergency_message": EMERGENCY_RESPONSE,
            "current_stage": "emergency",
            "messages": [{"role": "assistant", "content": EMERGENCY_RESPONSE}],
        }

    return {
        "is_emergency": False,
        "red_flags": [],
        "current_stage": "triaged",
    }
