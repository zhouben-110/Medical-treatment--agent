"""直接调用 medical_kb_mcp 知识层函数，组装医学上下文。"""

import asyncio
import logging

from medical_kb_mcp.db import search_diseases_by_symptoms, get_disease_detail
from medical_kb_mcp.vectors import search_guidelines

logger = logging.getLogger(__name__)


class MedicalRetriever:
    """通过直接函数调用检索医学知识库，组装 prompt context。"""

    async def retrieve_for_diagnosis(self, symptoms: list[str]) -> str:
        parts: list[str] = []
        query = "症状：" + "、".join(symptoms) + " 可能的疾病"

        # 结构化匹配与向量检索并行
        disease_result, guideline_result = await asyncio.gather(
            search_diseases_by_symptoms(symptoms),
            search_guidelines(query, k=3),
            return_exceptions=True,
        )

        if isinstance(disease_result, Exception):
            logger.warning("search_diseases_by_symptoms failed: %s", disease_result)
        elif disease_result:
            lines = ["【知识库匹配结果】"]
            for i, d in enumerate(disease_result, 1):
                lines.append(
                    f"{i}. {d.name}（匹配度{d.match_score*100:.0f}%，严重程度：{d.severity}）\n"
                    f"   匹配症状：{'、'.join(d.matched_symptoms)}\n"
                    f"   描述：{d.description}"
                )
            parts.append("\n".join(lines))

        if isinstance(guideline_result, Exception):
            logger.warning("search_guidelines failed: %s", guideline_result)
        elif guideline_result:
            lines = ["【医学文献参考】"]
            for i, c in enumerate(guideline_result[:3], 1):
                lines.append(f"{i}. {c.text[:200].strip()}...")
            parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""

    async def retrieve_for_advice(self, diseases: list[str], symptoms: list[str]) -> str:
        parts: list[str] = []
        top_diseases = diseases[:3]

        # 疾病详情和文献检索并行
        detail_tasks = [get_disease_detail(name) for name in top_diseases]
        merged_query = " ".join(f"{d} 治疗 用药 注意事项" for d in top_diseases[:2])
        guideline_task = search_guidelines(merged_query, k=3) if top_diseases else None

        tasks = detail_tasks + ([guideline_task] if guideline_task else [])
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理疾病详情
        for i, name in enumerate(top_diseases):
            result = results[i]
            if isinstance(result, Exception):
                logger.warning("get_disease_detail(%s) failed: %s", name, result)
            elif result:
                parts.append("\n".join([
                    f"【{result.name}】",
                    f"描述：{result.description}",
                    f"治疗建议：{result.treatment}",
                    f"就医指征：{result.when_to_see_doctor}",
                    f"严重程度：{result.severity}",
                ]))

        # 处理文献检索
        if guideline_task:
            guideline_result = results[len(top_diseases)]
            if isinstance(guideline_result, Exception):
                logger.warning("search_guidelines failed: %s", guideline_result)
            elif guideline_result:
                lines = ["【相关医学文献】"]
                for i, c in enumerate(guideline_result[:3], 1):
                    lines.append(f"{i}. {c.text[:300].strip()}")
                parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""
