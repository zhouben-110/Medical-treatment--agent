"""A/B 对比诊断管线：fixed vs agent。

依次在两种 pipeline 下跑 real eval，按 case_id 对齐结果，输出:
  - 整体指标对比表
  - case 级 diff（fixed 通过但 agent 失败 / 反之）
  - 仅 agent 路径会用到的工具调用统计

依赖：完整的 real 环境（DB / Redis / LLM API Key / ENABLE_AGENT_DIAGNOSE 可切换）。
mock 模式对两条管线没有区别，不要用。
"""

import asyncio
import os
import sys
import time
from typing import Iterable

from evals.metrics import EvalResult, EvalSummary
from evals.runner import run_eval_real
from evals.dataset import build_dataset


# ── 报告渲染 ──────────────────────────────────────────────────

W = 78

def _hr(char: str = "─") -> str:
    return char * W


def _row(label: str, fixed: str, agent: str, delta: str = "") -> str:
    return f"  {label:<28} │ {fixed:>14} │ {agent:>14} │ {delta:>10}"


def _delta_str(a: float, b: float, signed: bool = True, unit: str = "") -> str:
    """计算 agent 相对 fixed 的差值，正数表示更优方向依指标而定。"""
    d = b - a
    sign = "+" if d > 0 and signed else ""
    return f"{sign}{d:.3f}{unit}"


def _pct(x: float) -> str:
    return f"{x:.1%}"


def _num(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}"


def render_comparison(fixed: EvalSummary, agent: EvalSummary,
                      agent_tool_stats: dict) -> str:
    lines = []
    lines.append("")
    lines.append("═" * W)
    lines.append("  Pipeline A/B Comparison: fixed vs agent")
    lines.append("═" * W)
    lines.append(f"  Eval cases:  {fixed.total} (fixed)  /  {agent.total} (agent)")
    lines.append(f"  Wall time:   {fixed.elapsed_seconds:.1f}s (fixed)  /  "
                 f"{agent.elapsed_seconds:.1f}s (agent)")
    lines.append(f"  Per case:    {fixed.elapsed_seconds / max(fixed.total, 1):.2f}s (fixed)  /  "
                 f"{agent.elapsed_seconds / max(agent.total, 1):.2f}s (agent)")
    lines.append(_hr())
    lines.append("  " + "metric".ljust(28) + " │ " + "fixed".rjust(14)
                 + " │ " + "agent".rjust(14) + " │ " + "Δ (agent-fixed)".rjust(10))
    lines.append(_hr("─"))

    # 诊断命中率（越高越好）
    lines.append(_row(
        "Diagnostic hit rate",
        _pct(fixed.diagnostic_hit_rate),
        _pct(agent.diagnostic_hit_rate),
        _delta_str(fixed.diagnostic_hit_rate, agent.diagnostic_hit_rate),
    ))

    # 追问轮数（越低越好）
    lines.append(_row(
        "Avg question turns",
        _num(fixed.avg_question_turns),
        _num(agent.avg_question_turns),
        _delta_str(fixed.avg_question_turns, agent.avg_question_turns),
    ))

    # 急诊（越高越好）
    lines.append(_row(
        "Emergency recall",
        _pct(fixed.emergency_recall),
        _pct(agent.emergency_recall),
        _delta_str(fixed.emergency_recall, agent.emergency_recall),
    ))
    lines.append(_row(
        "Emergency precision",
        _pct(fixed.emergency_precision),
        _pct(agent.emergency_precision),
        _delta_str(fixed.emergency_precision, agent.emergency_precision),
    ))
    lines.append(_hr())

    # ── Agent 工具统计 ─────────────────────────────────────
    lines.append("  Agent 路径工具调用统计")
    lines.append(_hr("─"))
    for k, v in agent_tool_stats.items():
        lines.append(f"  {k:<28} │ {v}")
    lines.append("")

    # ── case 级 diff ───────────────────────────────────────
    fixed_by_id = {r.case_id: r for r in fixed.results}
    agent_by_id = {r.case_id: r for r in agent.results}

    only_fixed_pass = []   # fixed 命中、agent 失败
    only_agent_pass = []   # agent 命中、fixed 失败
    both_fail = []         # 都失败

    for cid in fixed_by_id:
        fr = fixed_by_id[cid]
        ar = agent_by_id.get(cid)
        if ar is None:
            continue
        if fr.passed and not ar.passed:
            only_fixed_pass.append((cid, fr, ar))
        elif ar.passed and not fr.passed:
            only_agent_pass.append((cid, fr, ar))
        elif not fr.passed and not ar.passed:
            both_fail.append((cid, fr, ar))

    if only_fixed_pass:
        lines.append("── fixed [OK] -> agent [FAIL] (regressions) ──")
        for cid, fr, ar in only_fixed_pass:
            lines.append(f"  [{cid}] {fr.expected_disease or '(emergency)'}  "
                         f"fixed got: {fr.actual_diseases[:3] or '(empty)'}  "
                         f"agent got: {ar.actual_diseases[:3] or '(empty)'}")
        lines.append("")

    if only_agent_pass:
        lines.append("── fixed [FAIL] -> agent [OK] (improvements) ──")
        for cid, fr, ar in only_agent_pass:
            lines.append(f"  [{cid}] {fr.expected_disease or '(emergency)'}  "
                         f"fixed got: {fr.actual_diseases[:3] or '(empty)'}  "
                         f"agent got: {ar.actual_diseases[:3] or '(empty)'}")
        lines.append("")

    if both_fail:
        lines.append(f"── both failed ({len(both_fail)} cases) ──")
        for cid, fr, ar in both_fail:
            lines.append(f"  [{cid}] {fr.expected_disease or '(emergency)'}  "
                         f"fixed: {fr.actual_diseases[:3] or '(empty)'}  "
                         f"agent: {ar.actual_diseases[:3] or '(empty)'}")
        lines.append("")

    # 错误明细
    errs = [r for r in agent.results if r.error]
    if errs:
        lines.append(f"── agent errors ({len(errs)}) ──")
        for r in errs[:5]:
            lines.append(f"  [{r.case_id}] {r.error[:120]}")
        lines.append("")

    lines.append("═" * W)
    return "\n".join(lines)


# ── Agent 路径：从 graph 状态里统计工具调用 ────────────────────

async def collect_agent_tool_stats(results: Iterable[EvalResult]) -> dict:
    """从 agent pipeline 跑完后的 checkpointer 状态里统计工具调用分布。

    每个 case 在 ainvoke 时分配独立 session_id（=thread_id），
    通过 EvalResult.session_id 反查 graph 持久化状态。
    """
    from app import graph as graph_module

    stats = {
        "cases using agent": 0,
        "submit w/o retrieval": 0,   # 即 finalize 的 FALLBACK_NO_EVIDENCE
        "avg tool calls/case": 0.0,
        "tool distribution": {},
    }
    total_calls = 0
    used = 0

    for r in results:
        if not r.session_id:
            continue
        cfg = {"configurable": {"thread_id": r.session_id}}
        try:
            st = await graph_module.medical_graph.aget_state(cfg)
        except Exception:
            continue
        if not st or not st.values:
            continue
        trace = st.values.get("tool_trace") or []
        if not trace:
            continue
        used += 1
        total_calls += len(trace)
        for t in trace:
            name = t.get("tool", "?")
            stats["tool distribution"][name] = stats["tool distribution"].get(name, 0) + 1

        # finalize 里 confidence=0.0 表示走了"无依据兜底"分支
        if not r.actual_diseases and trace:
            stats["submit w/o retrieval"] += 1

    if used:
        stats["cases using agent"] = used
        stats["avg tool calls/case"] = total_calls / used
    return stats


# ── 主流程 ────────────────────────────────────────────────────

async def run_both() -> tuple[EvalSummary, EvalSummary, dict]:
    print("▶ running fixed pipeline...", file=sys.stderr, flush=True)
    fixed = await run_eval_real(pipeline="fixed")
    print(f"  fixed done in {fixed.elapsed_seconds:.1f}s", file=sys.stderr, flush=True)

    print("▶ running agent pipeline...", file=sys.stderr, flush=True)
    agent = await run_eval_real(pipeline="agent")
    print(f"  agent done in {agent.elapsed_seconds:.1f}s", file=sys.stderr, flush=True)

    # 收集 agent 工具统计：直接从 EvalResult.session_id 反查 checkpointer
    tool_stats = await collect_agent_tool_stats(agent.results)
    return fixed, agent, tool_stats


async def main():
    # 强制从 .env 读 API Key
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Windows GBK 终端兜底：强制 UTF-8 避免 ✗/✓ 等字符报错
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    t0 = time.time()
    fixed, agent, tool_stats = await run_both()
    print(render_comparison(fixed, agent, tool_stats))
    print(f"\nTotal wall time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
