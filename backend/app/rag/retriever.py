"""统一检索接口：结构化数据 + 向量检索"""

from app.rag.knowledge_base import search_by_symptoms, search_by_disease


class MedicalRetriever:
    """合并结构化知识库和向量检索结果的统一接口"""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def retrieve_for_diagnosis(self, symptoms: list[str]) -> str:
        """diagnose 节点调用：用症状检索可能的疾病"""
        parts = []

        # 1. 结构化精确匹配
        structured = search_by_symptoms(symptoms)
        if structured:
            lines = ["【知识库匹配结果】"]
            for i, item in enumerate(structured, 1):
                lines.append(
                    f"{i}. {item['disease']}（匹配度{item['match_score']*100:.0f}%，"
                    f"严重程度：{item['severity']}）\n"
                    f"   匹配症状：{'、'.join(item['matched_symptoms'])}\n"
                    f"   描述：{item['description']}"
                )
            parts.append("\n".join(lines))

        # 2. 向量检索补充
        query = "症状：" + "、".join(symptoms) + " 可能的疾病"
        try:
            docs = await self.vector_store.ainvoke(query)
            if docs:
                lines = ["【医学文献参考】"]
                for i, doc in enumerate(docs[:3], 1):
                    text = doc.page_content[:200].replace("\n", " ")
                    lines.append(f"{i}. {text}...")
                parts.append("\n".join(lines))
        except Exception as e:
            print(f"[RAG] vector retrieve_for_diagnosis failed: {e}")

        return "\n\n".join(parts) if parts else ""

    async def retrieve_for_advice(self, diseases: list[str], symptoms: list[str]) -> str:
        """advise 节点调用：按疾病名检索治疗指南

        向量检索合并为单次查询，减少网络往返。
        """
        parts = []

        # 1. 结构化查详情
        for disease_name in diseases[:3]:
            detail = search_by_disease(disease_name)
            if detail:
                lines = [
                    f"【{detail['disease']}】",
                    f"描述：{detail['description']}",
                    f"治疗建议：{detail['treatment']}",
                    f"就医指征：{detail['when_to_see_doctor']}",
                    f"严重程度：{detail['severity']}",
                ]
                parts.append("\n".join(lines))

        # 2. 向量检索诊疗指南（合并为单次查询）
        if diseases:
            merged_query = " ".join(f"{d} 治疗 用药 注意事项" for d in diseases[:2])
            try:
                docs = await self.vector_store.ainvoke(merged_query)
                if docs:
                    lines = ["【相关医学文献】"]
                    for i, doc in enumerate(docs[:3], 1):
                        text = doc.page_content[:300].replace("\n", " ")
                        lines.append(f"{i}. {text}")
                    parts.append("\n".join(lines))
            except Exception as e:
                print(f"[RAG] vector retrieve_for_advice failed: {e}")

        return "\n\n".join(parts) if parts else ""
