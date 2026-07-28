"""Client-side orchestrator: directly calls Medical-KB functions (no MCP transport)."""

import logging
import asyncio
import hashlib
import json
from app.services.kb_service import (
    search_diseases_by_symptoms,
    get_disease_detail,
    search_guidelines,
)
from app.redis import cache_get, cache_set

logger = logging.getLogger(__name__)

TOOL_TIMEOUT = 10  # seconds per call


class MedicalRetriever:
    """Builds prompt context by composing Medical-KB functions directly (in-process)."""

    async def _search_diseases_cached(self, symptoms: list[str], limit: int = 5) -> list[dict]:
        """Call search_diseases_by_symptoms with Redis caching."""
        args_hash = hashlib.sha256(
            json.dumps({"symptoms": symptoms, "limit": limit}, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        cache_key = f"mc:tool:search_diseases_by_symptoms:{args_hash}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            matches = await asyncio.wait_for(
                search_diseases_by_symptoms(symptoms, limit), timeout=TOOL_TIMEOUT
            )
            result = [m.model_dump() for m in matches]
        except asyncio.TimeoutError:
            logger.warning(f"[retriever] search_diseases timed out after {TOOL_TIMEOUT}s")
            return []
        except Exception as e:
            logger.error(f"[retriever] search_diseases failed: {e}", exc_info=True)
            return []

        if result:
            await cache_set(cache_key, result, ttl=3600)
        return result

    async def _get_detail_cached(self, name: str) -> dict | None:
        """Call get_disease_detail with Redis caching."""
        args_hash = hashlib.sha256(name.encode()).hexdigest()[:16]
        cache_key = f"mc:tool:get_disease_detail:{args_hash}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            detail = await asyncio.wait_for(
                get_disease_detail(name), timeout=TOOL_TIMEOUT
            )
            result = detail.model_dump() if detail else None
        except asyncio.TimeoutError:
            logger.warning(f"[retriever] get_disease_detail timed out after {TOOL_TIMEOUT}s")
            return None
        except Exception as e:
            logger.error(f"[retriever] get_disease_detail failed: {e}", exc_info=True)
            return None

        if result:
            await cache_set(cache_key, result, ttl=86400)
        return result

    async def _search_guidelines_cached(self, query: str, k: int = 3) -> list[dict]:
        """Call search_guidelines with Redis caching."""
        args_hash = hashlib.sha256(
            json.dumps({"query": query, "k": k}, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        cache_key = f"mc:tool:search_guidelines:{args_hash}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            chunks = await asyncio.wait_for(
                search_guidelines(query, k), timeout=TOOL_TIMEOUT
            )
            result = [c.model_dump() for c in chunks]
        except asyncio.TimeoutError:
            logger.warning(f"[retriever] search_guidelines timed out after {TOOL_TIMEOUT}s")
            return []
        except Exception as e:
            logger.error(f"[retriever] search_guidelines failed: {e}", exc_info=True)
            return []

        if result:
            await cache_set(cache_key, result, ttl=3600)
        return result

    async def retrieve_for_diagnosis(self, symptoms: list[str]) -> tuple[str, list[str]]:
        """Returns (formatted_context, disease_name_list)."""
        parts: list[str] = []
        query = "症状：" + "、".join(symptoms) + " 可能的疾病"

        diseases, chunks = await asyncio.gather(
            self._search_diseases_cached(symptoms, 3),
            self._search_guidelines_cached(query, 2),
        )

        disease_names = []
        if diseases:
            lines = ["【知识库匹配】"]
            for i, d in enumerate(diseases[:3], 1):
                disease_names.append(d['name'])
                desc = d['description'].strip()
                lines.append(f"{i}. {d['name']}（混合评分: {d['match_score']:.2f}，严重度: {d['severity']}）：{desc}")
            parts.append("\n".join(lines))

        if chunks:
            lines = ["【诊疗指南文献参考】"]
            for i, c in enumerate(chunks[:2], 1):
                lines.append(f"{i}. {c['text'].strip()}")
            parts.append("\n".join(lines))

        return "\n".join(parts) if parts else "", disease_names

    async def retrieve_for_advice(self, diseases: list[str], symptoms: list[str]) -> str:
        parts: list[str] = []
        top_diseases = diseases[:3]

        # 疾病详情和文献检索全部并行
        detail_coros = [self._get_detail_cached(n) for n in top_diseases]
        merged = " ".join(f"{d} 治疗 用药 注意事项" for d in top_diseases[:2])
        guideline_coro = self._search_guidelines_cached(merged, 3) if top_diseases else None

        all_coros = detail_coros + ([guideline_coro] if guideline_coro else [])
        results = await asyncio.gather(*all_coros)

        for i, name in enumerate(top_diseases):
            detail = results[i]
            if detail:
                parts.append("\n".join([
                    f"【{detail['name']}】（严重度: {detail['severity']}）",
                    f"典型症状：{'、'.join(detail['symptoms'])}",
                    f"疾病简述：{detail['description']}",
                    f"治疗方案：{detail['treatment']}",
                    f"就医指征：{detail['when_to_see_doctor']}",
                ]))

        if guideline_coro:
            chunks = results[len(top_diseases)]
            if chunks:
                lines = ["【诊疗指南文献】"]
                for i, c in enumerate(chunks[:2], 1):
                    lines.append(f"{i}. {c['text'].strip()}")
                parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""
