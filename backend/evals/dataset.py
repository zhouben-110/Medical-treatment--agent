"""Eval 数据集：从 25 种疾病生成测试用例"""

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    case_id: str
    user_messages: list[str]
    expected_disease: str | None = None
    expected_is_emergency: bool = False
    category: str = "normal"  # "normal" | "emergency" | "ambiguous"


def build_dataset() -> list[EvalCase]:
    """构建完整 eval 数据集（25 正常 + 5 急诊 + 5 模糊 = 35 case）"""
    cases: list[EvalCase] = []

    # ── 正常 case：每种疾病 1 个 ─────────────────────────────
    normal_cases = [
        ("normal_01", "普通感冒", ["我发热、咳嗽、流鼻涕、打喷嚏，还有点头疼"]),
        ("normal_02", "流行性感冒", ["突然发高烧，全身肌肉酸痛，头疼得厉害，还畏寒"]),
        ("normal_03", "急性支气管炎", ["咳嗽好几天了，有痰，胸口闷，感觉气短"]),
        ("normal_04", "肺炎", ["发烧不退，咳嗽有痰，呼吸有点困难，胸口疼"]),
        ("normal_05", "支气管哮喘", ["喘不上气，胸闷，咳嗽，呼吸有哮鸣音"]),
        ("normal_06", "高血压", ["经常头疼头晕，心跳快，耳朵嗡嗡响，容易疲劳"]),
        ("normal_07", "冠心病", ["胸口闷痛，心跳不规律，气短，浑身没劲"]),
        ("normal_08", "心律失常", ["心跳忽快忽慢，胸口闷，头晕，乏力"]),
        ("normal_09", "急性胃肠炎", ["肚子疼，拉肚子，恶心想吐，还发烧了"]),
        ("normal_10", "胃溃疡", ["胃疼，胃胀，恶心不想吃饭，有时候想吐"]),
        ("normal_11", "胆囊炎", ["右上腹疼得厉害，恶心呕吐，发烧，不想吃东西"]),
        ("normal_12", "泌尿系统感染", ["尿频尿急尿痛，还发烧腰疼"]),
        ("normal_13", "糖尿病", ["最近喝水多、尿多、体重下降，容易累，视力也有点模糊"]),
        ("normal_14", "甲状腺功能亢进", ["心跳快，体重下降，手抖，出汗多，睡不着觉"]),
        ("normal_15", "贫血", ["头晕乏力，脸色苍白，心跳快，气短，失眠"]),
        ("normal_16", "颈椎病", ["脖子肩膀疼，头疼头晕，手麻"]),
        ("normal_17", "腰椎间盘突出", ["腰疼得厉害，腿麻，肌肉酸痛"]),
        ("normal_18", "关节炎", ["关节疼，肿了，肌肉酸痛，没力气"]),
        ("normal_19", "焦虑症", ["睡不着觉，心跳快，胸闷，头晕，没食欲"]),
        ("normal_20", "抑郁症", ["失眠，什么都不想干，没食欲，体重下降，头晕"]),
        ("normal_21", "荨麻疹", ["身上起了好多红疹子，特别痒，皮肤肿了"]),
        ("normal_22", "湿疹", ["皮肤起疹子，很痒，红肿，还脱皮"]),
        ("normal_23", "过敏性鼻炎", ["鼻子不通气，流清鼻涕，打喷嚏，头疼"]),
        ("normal_24", "偏头痛", ["头疼得厉害，一阵一阵的，恶心想吐，看东西模糊"]),
        ("normal_25", "中暑", ["在太阳底下待久了，头晕恶心，浑身没劲，肌肉酸疼，还发烧了"]),
    ]
    for cid, disease, msgs in normal_cases:
        cases.append(EvalCase(
            case_id=cid,
            user_messages=msgs,
            expected_disease=disease,
            expected_is_emergency=False,
            category="normal",
        ))

    # ── 急诊 case ────────────────────────────────────────────
    emergency_cases = [
        ("emg_01", "胸痛剧烈，大汗淋漓，有濒死感"),
        ("emg_02", "突然一侧肢体无力，口齿不清，嘴角歪斜"),
        ("emg_03", "呼吸困难，嘴唇发紫，喘不过气"),
        ("emg_04", "呕血不止，头晕目眩"),
        ("emg_05", "高热40度，意识模糊，抽搐"),
    ]
    for cid, msg in emergency_cases:
        cases.append(EvalCase(
            case_id=cid,
            user_messages=[msg],
            expected_disease=None,
            expected_is_emergency=True,
            category="emergency",
        ))

    # ── 模糊 case：症状不典型或跨疾病 ────────────────────────
    ambiguous_cases = [
        ("amb_01", "有点不舒服，说不上来哪里难受", None),
        ("amb_02", "最近总觉得累，偶尔有点头晕", None),
        ("amb_03", "肚子不太舒服，有时候疼有时候不疼", None),
        ("amb_04", "浑身没劲，睡眠不好，心情也不好", None),
        ("amb_05", "偶尔心跳快，偶尔头疼", None),
    ]
    for cid, msg, disease in ambiguous_cases:
        cases.append(EvalCase(
            case_id=cid,
            user_messages=[msg],
            expected_disease=disease,
            expected_is_emergency=False,
            category="ambiguous",
        ))

    return cases
