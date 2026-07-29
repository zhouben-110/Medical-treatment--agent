"""自主诊断 Agent：LLM 自行决定调用哪些知识库工具、调几次，直至提交结论。

与旧的 diagnose_and_advise 固定管线的区别：
- 检索序列由模型决定，不再硬编码「先查疾病再查详情」
- 通过 submit_diagnosis 工具收口，既拿到结构化输出又获得终止信号
- 安全红线（safety_rules）仍在 finalize 节点后置执行，不交给模型

外层复合缓存被去掉了（工具粒度缓存仍在 kb_tools 内），因此延迟会高于
固定管线，换来的是检索策略随病情自适应。
"""

import json
import logging
import time

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.state import MedicalAgentState
from app.llm import get_llm
from app.tools.kb_tools import KB_TOOLS, SUBMIT_TOOL_NAME, RETRIEVAL_TOOLS, RETRIEVAL_TOOL_NAMES
from app.safety_rules import intercept_contraindications

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5      # 最多 5 轮工具调用
WALL_CLOCK_BUDGET = 45.0     # 整个 Agent 循环的墙钟预算（秒）

DIAGNOSE_SYSTEM_PROMPT = """你是一个严谨的医疗AI助手。你的任务是基于知识库检索结果给出诊断建议。

已识别症状: {symptoms}
患者画像: {profile}

工作方式：
1. 你可以自主调用工具检索医学知识，调用顺序和次数由你决定。
2. 症状明确时，一次 search_diseases 可能就够；症状不典型、候选疾病评分接近、
   或涉及儿童/孕妇用药时，应追加 search_guidelines 核实。
3. 需要给出具体用药建议时，用 get_disease_detail 查该疾病的治疗方案。
4. 收集到足够依据后，调用 submit_diagnosis 提交结论。

硬性要求：
- 所有疾病名和治疗方案必须来自工具返回结果，禁止凭记忆作答。
- 若工具返回为空或评分都很低，仍调用 submit_diagnosis，
  但在 reasoning 里说明知识库无匹配依据，need_doctor 填 true。
- 最多 {max_iter} 轮工具调用，请高效安排。"""


def _extract_last_ai(scratchpad: list):
    for m in reversed(scratchpad or []):
        if getattr(m, "type", None) == "ai":
            return m
    return None


async def diagnose_agent(state: MedicalAgentState) -> dict:
    """Agent 推理节点：决定下一步调工具还是提交结论。"""
    scratchpad = list(state.get("diagnose_scratchpad") or [])

    updates: dict = {}
    if not scratchpad:
        # 首次进入：注入 system prompt 并记录起始时间
        profile = state.get("patient_profile") or {}
        profile_desc = (
            f"年龄段={profile.get('age_group') or '未知'}, "
            f"孕产哺乳={profile.get('is_pregnant') if profile.get('is_pregnant') is not None else '未知'}, "
            f"过敏史={'、'.join(profile.get('allergies') or []) or '无'}"
        )
        system = SystemMessage(content=DIAGNOSE_SYSTEM_PROMPT.format(
            symptoms="、".join(state.get("symptoms", [])) or "（无）",
            profile=profile_desc,
            max_iter=MAX_TOOL_ITERATIONS,
        ))
        scratchpad = [system]
        updates["diagnose_started_at"] = time.monotonic()

    llm = get_llm(temperature=0.3).bind_tools(KB_TOOLS)
    try:
        response = await llm.ainvoke(scratchpad)
    except Exception as e:
        logger.error(f"诊断 Agent LLM 调用失败: {e}", exc_info=True)
        # 标记失败，路由据此直接收口
        return {"tool_iterations": state.get("tool_iterations", 0) + 1,
                "agent_llm_failed": True}

    new_msgs = scratchpad if len(scratchpad) == 1 and not state.get("diagnose_scratchpad") else []
    updates["diagnose_scratchpad"] = new_msgs + [response]
    updates["tool_iterations"] = state.get("tool_iterations", 0) + 1
    return updates


def route_after_agent(state: MedicalAgentState) -> str:
    """决定继续调工具还是收口。"""
    if state.get("agent_llm_failed"):
        return "finalize"

    last_ai = _extract_last_ai(state.get("diagnose_scratchpad") or [])
    tool_calls = getattr(last_ai, "tool_calls", None) or [] if last_ai else []

    # 模型主动提交 → 收口
    if any(c.get("name") == SUBMIT_TOOL_NAME for c in tool_calls):
        return "finalize"

    # 无工具调用（模型直接吐文本）→ 收口，由 finalize 校验依据
    if not tool_calls:
        return "finalize"

    # 预算耗尽 → 强制收口
    if state.get("tool_iterations", 0) >= MAX_TOOL_ITERATIONS:
        logger.warning("诊断 Agent 达到工具调用轮数上限，强制收口")
        return "finalize"

    started = state.get("diagnose_started_at")
    if started and (time.monotonic() - started) > WALL_CLOCK_BUDGET:
        logger.warning("诊断 Agent 超出墙钟预算，强制收口")
        return "finalize"

    return "tools"


# ── Tool 执行 + 审计留痕 ─────────────────────────────────────

def _summarize_returned(value) -> str:
    """把工具返回值压缩成可审计的字符串摘要，避免 trace 体积爆炸。"""
    try:
        if isinstance(value, str):
            return value[:200]
        s = json.dumps(value, ensure_ascii=False)
        return s[:200]
    except Exception:
        return str(type(value).__name__)


async def tool_executor_node(state: MedicalAgentState) -> dict:
    """调 ToolNode 执行工具调用，并把每次调用追加进 tool_trace。

    ToolNode 自动构造 ToolMessage 并返回 list[ToolMessage]，与 scratchpad
    的 add_messages reducer 兼容。submit_diagnosis 是同步工具，结果
    是 "诊断已提交"，但仍走 ToolNode 统一处理。
    """
    last_ai = _extract_last_ai(state.get("diagnose_scratchpad") or [])
    tool_calls = getattr(last_ai, "tool_calls", None) or []
    if not tool_calls:
        return {}

    inner = ToolNode(KB_TOOLS, handle_tool_errors=True)
    tool_messages = await inner.ainvoke(state)
    # tool_messages 是 dict 或 list[ToolMessage]，统一规整为 list
    if isinstance(tool_messages, dict):
        msgs = tool_messages.get("messages", [])
    else:
        msgs = tool_messages

    # 审计：按 tool_call_id 对应 tool_call 与 ToolMessage 返回值
    trace = list(state.get("tool_trace") or [])
    call_by_id = {c["id"]: c for c in tool_calls}
    for tm in msgs:
        cid = getattr(tm, "tool_call_id", None)
        call = call_by_id.get(cid, {})
        # 工具返回值在 tm.content 里
        raw = getattr(tm, "content", "")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            parsed = raw
        trace.append({
            "tool": call.get("name"),
            "args": call.get("args"),
            "returned": _summarize_returned(parsed),
        })

    # tool_messages 本身通过 scratchpad 的 add_messages reducer 累积
    return {
        "diagnose_scratchpad": msgs,
        "tool_trace": trace,
    }


# ── 收口：校验依据 → 安全拦截 → 写用户消息 → 清空 scratchpad ─

FALLBACK_NO_EVIDENCE = (
    "抱歉，我在医学知识库中没有找到与您描述的症状匹配的依据，"
    "无法给出可靠的诊断建议。建议您直接前往医院或在线咨询执业医生。"
)

DISCLAIMER = "\n\n以上内容仅供参考，不构成医疗建议。如有不适，请及时就医。"


def _format_submission(submitted_args: dict, evidence: str) -> tuple[str, str, bool]:
    """把 submit_diagnosis 的参数格式化为用户可见的诊断文本。"""
    diseases = submitted_args.get("possible_diseases") or []
    reasoning = submitted_args.get("reasoning", "")
    treatment = submitted_args.get("treatment_advice", "")
    need_doc = bool(submitted_args.get("need_doctor", True))

    parts = []
    if diseases:
        parts.append("**可能的疾病**：" + "、".join(diseases))
    if reasoning:
        parts.append("**判断依据**：" + reasoning)
    if treatment:
        parts.append("**治疗建议**：" + treatment)
    if not need_doc:
        parts.append("**就医建议**：症状较轻，居家观察即可；如出现加重请及时就医。")
    else:
        parts.append("**就医建议**：建议尽快就医或在线咨询执业医生。")

    # 附检索依据摘要，便于审计与前端展示
    if evidence:
        parts.append("\n---\n**知识库检索依据**\n" + evidence)
    return "\n\n".join(parts), "、".join(diseases), need_doc


def _collect_evidence_trace(trace: list[dict]) -> str:
    """把 tool_trace 压缩成简短的「依据」文本，附在诊断后供审计。"""
    lines = []
    for i, t in enumerate(trace, 1):
        tool = t.get("tool")
        if tool in ("search_diseases", "search_guidelines"):
            args = t.get("args") or {}
            q = args.get("symptoms") or args.get("query") or ""
            lines.append(f"  {i}. 调 {tool}：{str(q)[:60]} → {t.get('returned', '')[:120]}")
        elif tool == "get_disease_detail":
            lines.append(f"  {i}. 调 get_disease_detail：{t.get('args', {}).get('name', '')}")
    return "\n".join(lines) if lines else ""


async def finalize_diagnosis(state: MedicalAgentState) -> dict:
    """从 scratchpad 提取 submit_diagnosis 参数，过滤掉凭记忆作答的情况。"""
    trace = state.get("tool_trace") or []
    retrieved_tools_used = [t for t in trace if t.get("tool") in RETRIEVAL_TOOL_NAMES and t.get("tool") not in (None,)]

    # 找到最后一条 AI 消息里的 submit_diagnosis 调用
    last_ai = _extract_last_ai(state.get("diagnose_scratchpad") or [])
    submitted_args = None
    if last_ai:
        for c in (getattr(last_ai, "tool_calls", None) or []):
            if c.get("name") == SUBMIT_TOOL_NAME:
                submitted_args = c.get("args", {})
                break

    # 情形 1：模型调了 submit_diagnosis 但没调过任何检索工具
    if submitted_args and not retrieved_tools_used:
        return {
            "possible_diseases": [],
            "confidence": 0.0,
            "treatment_plan": FALLBACK_NO_EVIDENCE + DISCLAIMER,
            "current_stage": "completed",
            "retrieved_context": "",
            "messages": [{"role": "assistant", "content": FALLBACK_NO_EVIDENCE + DISCLAIMER}],
            "diagnose_scratchpad": [],
        }

    # 情形 2：正常提交
    if submitted_args:
        evidence = _collect_evidence_trace(retrieved_tools_used)
        text, diseases_csv, need_doc = _format_submission(submitted_args, evidence)
        text = intercept_contraindications(text, state.get("patient_profile"))
        if DISCLAIMER.lstrip() not in text:
            text = text + DISCLAIMER
        return {
            "possible_diseases": diseases_csv.split("、") if diseases_csv else [],
            "confidence": 0.7 if retrieved_tools_used else 0.4,
            "treatment_plan": text,
            "current_stage": "completed",
            "retrieved_context": _collect_evidence_trace(trace),
            "messages": [{"role": "assistant", "content": text}],
            "diagnose_scratchpad": [],
        }

    # 情形 3：模型既没调检索工具也没调 submit_diagnosis（直接吐文本或 LLM 失败）
    fallback = FALLBACK_NO_EVIDENCE + DISCLAIMER
    return {
        "possible_diseases": [],
        "confidence": 0.0,
        "treatment_plan": fallback,
        "current_stage": "completed",
        "retrieved_context": "",
        "messages": [{"role": "assistant", "content": fallback}],
        "diagnose_scratchpad": [],
    }

