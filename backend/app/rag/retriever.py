"""Client-side orchestrator: calls atomic MCP tools, assembles medical_context."""

import asyncio
import json
from app.mcp_client import get_tool

TOOL_TIMEOUT = 10  # seconds per MCP tool call


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
            raw = await asyncio.wait_for(tool.ainvoke(args), timeout=TOOL_TIMEOUT)
            return _parse_tool_result(raw)
        except asyncio.TimeoutError:
            print(f"[retriever] tool {name} timed out after {TOOL_TIMEOUT}s")
            return []
        except Exception as e:
            print(f"[retriever] tool {name} failed: {e}")
            return []

    async def retrieve_for_diagnosis(self, symptoms: list[str]) -> tuple[str, list[str]]:
        """Returns (formatted_context, disease_name_list)."""
        parts: list[str] = []
        query = "症状：" + "、".join(symptoms) + " 可能的疾病"

        diseases, chunks = await asyncio.gather(
            self._call("search_diseases_by_symptoms", {"symptoms": symptoms, "limit": 3}),
            self._call("search_guidelines", {"query": query, "k": 2}),
        )

        disease_names = []
        if diseases:
            lines = ["【知识库匹配】"]
            for i, d in enumerate(diseases[:3], 1):
                disease_names.append(d['name'])
                desc = d['description'][:80]
                lines.append(f"{i}. {d['name']}（{d['match_score']*100:.0f}%，{d['severity']}）{desc}")
            parts.append("\n".join(lines))

        if chunks:
            lines = ["【文献参考】"]
            for i, c in enumerate(chunks[:2], 1):
                lines.append(f"{i}. {c['text'][:120].strip()}")
            parts.append("\n".join(lines))

        return "\n".join(parts) if parts else "", disease_names

    async def retrieve_for_advice(self, diseases: list[str], symptoms: list[str]) -> str:
        parts: list[str] = []
        top_diseases = diseases[:3]

        # 疾病详情和文献检索全部并行
        detail_coros = [self._call("get_disease_detail", {"name": n}) for n in top_diseases]
        merged = " ".join(f"{d} 治疗 用药 注意事项" for d in top_diseases[:2])
        guideline_coro = self._call("search_guidelines", {"query": merged, "k": 3}) if top_diseases else None

        all_coros = detail_coros + ([guideline_coro] if guideline_coro else [])
        results = await asyncio.gather(*all_coros)

        for i, name in enumerate(top_diseases):
            details = results[i]
            detail = details[0] if details else None
            if detail:
                parts.append("\n".join([
                    f"【{detail['name']}】（{detail['severity']}）",
                    f"治疗：{detail['treatment'][:120]}",
                    f"就医指征：{detail['when_to_see_doctor'][:80]}",
                ]))

        if guideline_coro:
            chunks = results[len(top_diseases)]
            if chunks:
                lines = ["【文献】"]
                for i, c in enumerate(chunks[:2], 1):
                    lines.append(f"{i}. {c['text'][:150].strip()}")
                parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""
