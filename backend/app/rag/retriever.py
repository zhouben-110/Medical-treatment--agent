"""Client-side orchestrator: calls atomic MCP tools, assembles medical_context."""

import json
from app.mcp_client import get_tool


def _parse_tool_result(raw) -> list:
    """Normalize langchain-mcp-adapters output into a list of dict items.

    The adapter returns a list of content blocks — ``[{'type':'text','text':<json>}, ...]`` —
    one block per item the tool returned, or ``[]`` when there are no results. We also
    tolerate a raw JSON string or already-parsed data for robustness across versions.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    if isinstance(raw, list):
        items = []
        for el in raw:
            if isinstance(el, dict) and el.get("type") == "text" and "text" in el:
                items.append(json.loads(el["text"]))
            else:
                items.append(el)
        return items
    return [raw]


class MedicalRetriever:
    """Builds prompt context by composing the Medical-KB MCP tools."""

    def __init__(self, tools: list):
        self.tools = tools or []

    async def _call(self, name: str, args: dict) -> list:
        tool = get_tool(self.tools, name)
        if tool is None:
            return []
        try:
            raw = await tool.ainvoke(args)
            return _parse_tool_result(raw)
        except Exception as e:
            print(f"[retriever] tool {name} failed: {e}")
            return []

    async def retrieve_for_diagnosis(self, symptoms: list[str]) -> str:
        parts: list[str] = []

        diseases = await self._call("search_diseases_by_symptoms", {"symptoms": symptoms})
        if diseases:
            lines = ["【知识库匹配结果】"]
            for i, d in enumerate(diseases, 1):
                lines.append(
                    f"{i}. {d['name']}（匹配度{d['match_score']*100:.0f}%，严重程度：{d['severity']}）\n"
                    f"   匹配症状：{'、'.join(d['matched_symptoms'])}\n"
                    f"   描述：{d['description']}"
                )
            parts.append("\n".join(lines))

        query = "症状：" + "、".join(symptoms) + " 可能的疾病"
        chunks = await self._call("search_guidelines", {"query": query, "k": 3})
        if chunks:
            lines = ["【医学文献参考】"]
            for i, c in enumerate(chunks[:3], 1):
                lines.append(f"{i}. {c['text'][:200].strip()}...")
            parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""

    async def retrieve_for_advice(self, diseases: list[str], symptoms: list[str]) -> str:
        parts: list[str] = []

        for name in diseases[:3]:
            details = await self._call("get_disease_detail", {"name": name})
            detail = details[0] if details else None
            if detail:
                parts.append("\n".join([
                    f"【{detail['name']}】",
                    f"描述：{detail['description']}",
                    f"治疗建议：{detail['treatment']}",
                    f"就医指征：{detail['when_to_see_doctor']}",
                    f"严重程度：{detail['severity']}",
                ]))

        if diseases:
            merged = " ".join(f"{d} 治疗 用药 注意事项" for d in diseases[:2])
            chunks = await self._call("search_guidelines", {"query": merged, "k": 3})
            if chunks:
                lines = ["【相关医学文献】"]
                for i, c in enumerate(chunks[:3], 1):
                    lines.append(f"{i}. {c['text'][:300].strip()}")
                parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""
