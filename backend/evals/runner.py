"""Eval 执行引擎：支持 mock（快速 CI）和 real（完整 E2E）两种模式"""

import time
import re
from evals.dataset import EvalCase, build_dataset
from evals.metrics import EvalResult, EvalSummary, compute_summary
from app.nodes.triage import _check_red_flags


# ── Mock 模式：纯规则匹配，无外部依赖 ────────────────────────

def _simple_extract_symptoms(text: str) -> list[str]:
    """简单的症状关键词提取"""
    symptom_keywords = [
        "发热", "发烧", "咳嗽", "流涕", "鼻塞", "头痛", "头疼", "乏力",
        "咽痛", "打喷嚏", "肌肉酸痛", "寒战", "咳痰", "胸闷", "气短",
        "呼吸困难", "胸痛", "喘息", "头晕", "心悸", "耳鸣", "视力模糊",
        "腹痛", "腹泻", "恶心", "呕吐", "食欲不振", "胃胀", "发热",
        "尿频", "尿急", "尿痛", "腰痛", "多饮", "多尿", "体重变化",
        "失眠", "手抖", "多汗", "面色苍白", "颈肩痛", "手脚麻木",
        "关节痛", "肿胀", "皮疹", "瘙痒", "红肿", "脱皮", "流涕",
        "胸闷痛", "咳血", "肌肉酸疼",
    ]
    found = []
    for kw in symptom_keywords:
        if kw in text:
            found.append(kw)
    return found


def _mock_disease_match(symptoms: list[str]) -> list[str]:
    """基于症状关键词的简单疾病匹配（模拟 MCP 检索）"""
    from medical_kb_mcp.seed_diseases import DISEASE_KNOWLEDGE

    scored = []
    for entry in DISEASE_KNOWLEDGE:
        disease_symptoms = set(entry["symptoms"])
        # 扩展匹配：将常见同义词映射
        expanded = set(symptoms)
        for s in symptoms:
            if s in ("头疼", "头痛"):
                expanded.add("头痛")
            if s in ("发烧", "发热"):
                expanded.add("发热")
            if s in ("肌肉酸疼", "肌肉酸痛"):
                expanded.add("肌肉酸痛")
            if s in ("流鼻涕", "流涕"):
                expanded.add("流涕")

        overlap = len(disease_symptoms & expanded)
        if overlap > 0:
            # Dice similarity
            score = 2 * overlap / (len(disease_symptoms) + len(expanded))
            scored.append((entry["disease"], score))

    scored.sort(key=lambda x: -x[1])
    return [name for name, _ in scored[:3]]


async def run_single_mock(case: EvalCase) -> EvalResult:
    """Mock 模式下运行单个 eval case"""
    user_msg = case.user_messages[0]

    # 1. 急诊检测（用真实红旗检测逻辑）
    red_flags = _check_red_flags(user_msg)
    is_emergency = len(red_flags) > 0

    # 2. 如果是急诊，直接返回
    if case.expected_is_emergency:
        return EvalResult(
            case_id=case.case_id,
            category=case.category,
            expected_disease=None,
            actual_diseases=[],
            is_emergency_expected=True,
            is_emergency_actual=is_emergency,
            question_turns=0,
            passed=is_emergency,
        )

    # 3. 非急诊：提取症状 → 匹配疾病
    if is_emergency:
        # 误检为急诊
        return EvalResult(
            case_id=case.case_id,
            category=case.category,
            expected_disease=case.expected_disease,
            actual_diseases=[],
            is_emergency_expected=False,
            is_emergency_actual=True,
            question_turns=0,
            passed=False,
        )

    symptoms = _simple_extract_symptoms(user_msg)
    diseases = _mock_disease_match(symptoms)

    # 模拟追问：如果症状少于 3 个，需要 1 轮追问
    question_turns = 1 if len(symptoms) < 3 else 0

    hit = case.expected_disease in diseases if case.expected_disease else True
    return EvalResult(
        case_id=case.case_id,
        category=case.category,
        expected_disease=case.expected_disease,
        actual_diseases=diseases,
        is_emergency_expected=False,
        is_emergency_actual=False,
        question_turns=question_turns,
        passed=hit,
    )


async def run_eval_mock() -> EvalSummary:
    """Mock 模式：运行全部 eval case"""
    cases = build_dataset()
    start = time.time()
    results = []
    for case in cases:
        result = await run_single_mock(case)
        results.append(result)
    elapsed = time.time() - start
    return compute_summary(results, elapsed)


# ── Real 模式：调真实 graph（需要 DB + MCP + LLM）────────────

async def run_single_real(case: EvalCase) -> EvalResult:
    """Real 模式下运行单个 eval case（需要完整环境）"""
    from app import graph as graph_module
    import uuid

    if graph_module.medical_graph is None:
        raise RuntimeError("Graph not initialized. Start the app first or use mode='mock'.")

    session_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": session_id}}

    # 构建初始 state
    graph_input = {
        "messages": [{"role": "user", "content": case.user_messages[0]}],
        "symptoms": [],
        "current_stage": "start",
        "confidence": 0.0,
        "possible_diseases": [],
        "treatment_plan": "",
        "need_more_info": True,
        "session_id": session_id,
        "retrieved_context": "",
        "is_emergency": False,
        "red_flags": [],
        "emergency_message": "",
    }

    try:
        result = await graph_module.medical_graph.ainvoke(graph_input, config=cfg)
    except Exception as e:
        return EvalResult(
            case_id=case.case_id,
            category=case.category,
            expected_disease=case.expected_disease,
            actual_diseases=[],
            is_emergency_expected=case.expected_is_emergency,
            is_emergency_actual=False,
            question_turns=0,
            passed=False,
            error=str(e),
        )

    is_emergency = result.get("is_emergency", False)
    diseases = result.get("possible_diseases", [])
    stage = result.get("current_stage", "")

    # 计算追问轮数：通过检查 graph 历史中的 question 节点
    question_turns = 0
    try:
        state = await graph_module.medical_graph.aget_state(cfg)
        for snap in (state.metadata.get("checkpoints", []) if state.metadata else []):
            if "question" in str(snap):
                question_turns += 1
    except Exception:
        pass

    if case.expected_is_emergency:
        passed = is_emergency
    elif case.expected_disease:
        passed = case.expected_disease in diseases
    else:
        passed = True  # ambiguous case

    return EvalResult(
        case_id=case.case_id,
        category=case.category,
        expected_disease=case.expected_disease,
        actual_diseases=diseases,
        is_emergency_expected=case.expected_is_emergency,
        is_emergency_actual=is_emergency,
        question_turns=question_turns,
        passed=passed,
    )


async def run_eval_real() -> EvalSummary:
    """Real 模式：运行全部 eval case"""
    cases = build_dataset()
    start = time.time()
    results = []
    for case in cases:
        result = await run_single_real(case)
        results.append(result)
    elapsed = time.time() - start
    return compute_summary(results, elapsed)


# ── 统一入口 ─────────────────────────────────────────────────

async def run_eval(mode: str = "mock") -> EvalSummary:
    """统一 eval 入口

    Args:
        mode: "mock" (快速, CI) 或 "real" (完整 E2E)
    """
    if mode == "mock":
        return await run_eval_mock()
    elif mode == "real":
        return await run_eval_real()
    else:
        raise ValueError(f"Unknown eval mode: {mode}. Use 'mock' or 'real'.")
