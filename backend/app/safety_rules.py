"""用药安全红线规则与拦截器"""

import re
import logging

logger = logging.getLogger(__name__)

# 孕妇及哺乳期禁用/慎用药物关键词及说明
PREGNANCY_CONTRAINDICATED = {
    "沙星": "喹诺酮类抗生素（如左氧氟沙星、莫西沙星）可能影响胎儿软骨发育。",
    "左氧氟沙星": "喹诺酮类抗生素（如左氧氟沙星、莫西沙星）可能影响胎儿软骨发育。",
    "莫西沙星": "喹诺酮类抗生素（如左氧氟沙星、莫西沙星）可能影响胎儿软骨发育。",
    "诺氟沙星": "喹诺酮类抗生素（如左氧氟沙星、莫西沙星）可能影响胎儿软骨发育。",
    "布洛芬": "非斯特类抗炎药（如布洛芬、双氯芬酸）在孕晚期可能导致胎儿动脉导管提前闭合。",
    "阿司匹林": "水杨酸类药物可能增加孕期出血风险并影响胎儿发育。",
    "双氯芬酸": "非斯特类抗炎药（如布洛芬、双氯芬酸）在孕晚期可能导致胎儿动脉导管提前闭合。",
    "沙坦": "血管紧张素II受体拮抗剂（如缬沙坦、氯沙坦）具有肾毒性和致畸性。",
    "普利": "血管紧张素转换酶抑制剂（如依那普利、贝那普利）具有肾毒性和致畸性。",
    "四环素": "四环素类药物可能导致胎儿牙齿黄染和骨骼发育迟缓。",
    "多西环素": "四环素类药物可能导致胎儿牙齿黄染和骨骼发育迟缓。",
    "利巴韦林": "该药物具有极强的致畸性，孕妇及备孕期女性禁用。",
}

# 儿童/婴儿禁用/慎用药物及说明
CHILD_CONTRAINDICATED = {
    "沙星": "喹诺酮类药物（如左氧氟沙星、诺氟沙星）可能对儿童软骨发育造成损害，18岁以下禁用。",
    "左氧氟沙星": "喹诺酮类药物（如左氧氟沙星、诺氟沙星）可能对儿童软骨发育造成损害，18岁以下禁用。",
    "诺氟沙星": "喹诺酮类药物（如左氧氟沙星、诺氟沙星）可能对儿童软骨发育造成损害，18岁以下禁用。",
    "莫西沙星": "喹诺酮类药物（如左氧氟沙星、诺氟沙星）可能对儿童软骨发育造成损害，18岁以下禁用。",
    "阿司匹林": "儿童使用阿司匹林治疗病毒感染可能诱发致命的瑞氏综合征（Reye Syndrome）。",
    "四环素": "8岁以下儿童使用四环素类药物可能导致永久性牙齿黄染（四环素牙）及骨骼发育抑制。",
    "多西环素": "8岁以下儿童使用多西环素可能导致永久性牙齿黄染（四环素牙）及骨骼发育抑制。",
    "米诺环素": "8岁以下儿童使用米诺环素可能导致永久性牙齿黄染（四环素牙）及骨骼发育抑制。",
    "庆大霉素": "氨基糖苷类抗生素（如庆大霉素、链霉素）具有耳毒性和肾毒性，儿童需极度慎用。",
    "链霉素": "氨基糖苷类抗生素（如庆大霉素、链霉素）具有耳毒性和肾毒性，儿童需极度慎用。",
}


def intercept_contraindications(advice: str, profile: dict | None) -> str:
    """用药红线安全拦截器。
    根据患者的 age_group, is_pregnant, allergies 对 LLM 生成的诊断建议进行安全扫描和警告注入。
    """
    if not advice or not profile:
        return advice

    warnings = []

    # 1. 检查孕妇/哺乳期限制
    if profile.get("is_pregnant") is True:
        matched_preg = []
        for kw, reason in PREGNANCY_CONTRAINDICATED.items():
            if kw in advice:
                matched_preg.append(f"“{kw}”（原因：{reason}）")
        if matched_preg:
            warnings.append(
                "⚠️ **用药警示 (孕产安全)**：监测到您可能处于备孕、怀孕或哺乳期，而生成的建议中包含了该群体禁忌或需慎用的药物：\n"
                + "\n".join(f"  * {item}" for item in matched_preg)
                + "\n  请绝对不要自行服用以上药物，必须在专业医生指导下进行治疗！"
            )

    # 2. 检查儿童限制
    age_group = profile.get("age_group")
    if age_group in ("婴儿", "儿童"):
        matched_child = []
        for kw, reason in CHILD_CONTRAINDICATED.items():
            if kw in advice:
                matched_child.append(f"“{kw}”（原因：{reason}）")
        if matched_child:
            warnings.append(
                f"⚠️ **用药警示 (儿童安全)**：监测到患者为{age_group}，而生成的建议中包含了儿童禁忌或需慎用的药物：\n"
                + "\n".join(f"  * {item}" for item in matched_child)
                + "\n  请勿给儿童使用上述药物，应及时就医并遵医嘱！"
            )

    # 3. 检查药物过敏史
    allergies = profile.get("allergies") or []
    if allergies:
        matched_allergies = []
        # 直接匹配
        for allergy in allergies:
            if not allergy:
                continue
            # 基础关键词匹配
            if allergy in advice:
                matched_allergies.append(f"“{allergy}”")
            # 常见交叉过敏匹配，如青霉素过敏提示阿莫西林
            elif allergy == "青霉素" and ("阿莫西林" in advice or "氨苄西林" in advice or "哌拉西林" in advice):
                matched_allergies.append("“阿莫西林/青霉素类药物” (青霉素过敏者禁用)")
            elif allergy == "头孢" and "头孢" in advice:
                matched_allergies.append("“头孢类抗生素” (头孢过敏者禁用)")

        if matched_allergies:
            warnings.append(
                "⚠️ **用药警示 (过敏风险)**：监测到您登记有以下药物过敏史：`" + "、".join(allergies) + "`，"
                "而生成的建议中包含了可能引起过敏的药物或同类药物：\n"
                + "\n".join(f"  * {item}" for item in matched_allergies)
                + "\n  请绝对避免使用该药物，以免发生严重过敏反应！"
            )

    # 如果有警告，将其插入到建议的末尾（在免责声明之前，或者作为一个高亮卡片附加）
    if warnings:
        warning_block = (
            "\n\n---\n\n"
            + "\n\n".join(warnings)
            + "\n\n"
        )
        # 尝试插在原有的免责声明之前
        disclaimer_marker = "以上内容仅供参考，不构成医疗建议"
        if disclaimer_marker in advice:
            parts = advice.split(disclaimer_marker, 1)
            # 重构 advice，在免责声明前加入警示块
            return parts[0].rstrip() + warning_block + disclaimer_marker + parts[1]
        else:
            return advice + warning_block

    return advice
