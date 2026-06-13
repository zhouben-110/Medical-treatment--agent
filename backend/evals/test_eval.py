"""M3: Eval 测试 — 量化 agent 质量指标"""

import pytest
from evals.runner import run_eval
from evals.dataset import build_dataset


# ── 数据集完整性 ─────────────────────────────────────────────

def test_dataset_has_35_cases():
    cases = build_dataset()
    assert len(cases) == 35


def test_dataset_normal_cases_have_expected_disease():
    cases = build_dataset()
    normal = [c for c in cases if c.category == "normal"]
    assert len(normal) == 25
    for c in normal:
        assert c.expected_disease is not None


def test_dataset_emergency_cases():
    cases = build_dataset()
    emg = [c for c in cases if c.category == "emergency"]
    assert len(emg) == 5
    for c in emg:
        assert c.expected_is_emergency is True


def test_dataset_ambiguous_cases():
    cases = build_dataset()
    amb = [c for c in cases if c.category == "ambiguous"]
    assert len(amb) == 5


# ── 核心指标断言 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_diagnostic_hit_rate():
    """诊断命中率 ≥ 60%"""
    summary = await run_eval(mode="mock")
    assert summary.diagnostic_hit_rate >= 0.6, (
        f"Diagnostic hit rate {summary.diagnostic_hit_rate:.1%} < 60%\n"
        + summary.format_report()
    )


@pytest.mark.asyncio
async def test_emergency_recall():
    """急症召回率 = 100%（不能漏检任何急诊）"""
    summary = await run_eval(mode="mock")
    assert summary.emergency_recall == 1.0, (
        f"Emergency recall {summary.emergency_recall:.1%} < 100%\n"
        + summary.format_report()
    )


@pytest.mark.asyncio
async def test_emergency_precision():
    """急症精确度 = 100%（不能误检非急诊为急诊）"""
    summary = await run_eval(mode="mock")
    assert summary.emergency_precision == 1.0, (
        f"Emergency precision {summary.emergency_precision:.1%} < 100%\n"
        + summary.format_report()
    )


@pytest.mark.asyncio
async def test_avg_question_turns():
    """平均追问轮数 < 3"""
    summary = await run_eval(mode="mock")
    assert summary.avg_question_turns < 3.0, (
        f"Avg question turns {summary.avg_question_turns:.1f} >= 3.0\n"
        + summary.format_report()
    )


# ── 报告输出（始终运行，不影响断言）────────────────────────

@pytest.mark.asyncio
async def test_eval_report(capsys):
    """打印完整 eval 报告"""
    summary = await run_eval(mode="mock")
    report = summary.format_report()
    print(report)
    # 确保报告格式正确
    assert "Diagnostic Hit Rate" in report
    assert "Emergency Recall" in report
    assert "Avg Question Turns" in report
