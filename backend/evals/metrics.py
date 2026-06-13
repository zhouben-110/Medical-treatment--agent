"""Eval 指标计算"""

from dataclasses import dataclass, field


@dataclass
class EvalResult:
    case_id: str
    category: str
    expected_disease: str | None
    actual_diseases: list[str]
    is_emergency_expected: bool
    is_emergency_actual: bool
    question_turns: int
    passed: bool
    error: str | None = None


@dataclass
class EvalSummary:
    total: int
    diagnostic_hit_rate: float
    avg_question_turns: float
    emergency_recall: float
    emergency_precision: float
    results: list[EvalResult]
    elapsed_seconds: float = 0.0

    def format_report(self) -> str:
        lines = [
            "",
            "═" * 50,
            "  Medical Agent Eval Report",
            "═" * 50,
            f"  Cases: {self.total} | Time: {self.elapsed_seconds:.1f}s",
            "",
            f"  Diagnostic Hit Rate:   {self.diagnostic_hit_rate:.1%}",
            f"  Avg Question Turns:    {self.avg_question_turns:.1f}",
            f"  Emergency Recall:      {self.emergency_recall:.1%}",
            f"  Emergency Precision:   {self.emergency_precision:.1%}",
        ]

        # 失败详情
        failures = [r for r in self.results if not r.passed and r.category != "ambiguous"]
        if failures:
            lines.append("")
            lines.append("── Failures ──")
            for r in failures:
                got = r.actual_diseases[:3] if r.actual_diseases else ["(empty)"]
                lines.append(f"  [{r.case_id}] {r.expected_disease} → got {got}")

        # 急诊详情
        emg_results = [r for r in self.results if r.category == "emergency"]
        if emg_results:
            lines.append("")
            lines.append("── Emergency Cases ──")
            for r in emg_results:
                mark = "[OK]" if r.is_emergency_actual else "[MISS]"
                lines.append(f"  [{r.case_id}] {mark} {'detected' if r.is_emergency_actual else 'MISSED'}")

        lines.append("")
        lines.append("═" * 50)
        return "\n".join(lines)


def compute_summary(results: list[EvalResult], elapsed: float = 0.0) -> EvalSummary:
    """从 eval 结果列表计算汇总指标"""
    total = len(results)

    # ── 诊断命中率（仅 normal case）──
    normal_results = [r for r in results if r.category == "normal" and r.expected_disease]
    hits = sum(
        1 for r in normal_results
        if r.expected_disease in (r.actual_diseases or [])
    )
    diagnostic_hit_rate = hits / len(normal_results) if normal_results else 0.0

    # ── 平均追问轮数（所有 case）──
    question_turns_list = [r.question_turns for r in results]
    avg_turns = sum(question_turns_list) / len(question_turns_list) if question_turns_list else 0.0

    # ── 急诊召回率 / 精确度 ──
    emg_expected = [r for r in results if r.is_emergency_expected]
    emg_actual = [r for r in results if r.is_emergency_actual]

    tp = sum(1 for r in emg_expected if r.is_emergency_actual)       # 应急且被检出
    fn = sum(1 for r in emg_expected if not r.is_emergency_actual)   # 应急但漏检
    fp = sum(1 for r in emg_actual if not r.is_emergency_expected)   # 非应急但误检

    emergency_recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    emergency_precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0

    return EvalSummary(
        total=total,
        diagnostic_hit_rate=diagnostic_hit_rate,
        avg_question_turns=avg_turns,
        emergency_recall=emergency_recall,
        emergency_precision=emergency_precision,
        results=results,
        elapsed_seconds=elapsed,
    )
