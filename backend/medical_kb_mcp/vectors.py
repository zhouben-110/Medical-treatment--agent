"""pgvector + DashScope guideline retrieval (moved out of app/rag)."""

import asyncio
import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy
from medical_kb_mcp.config import get_mcp_settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "medical_guidelines"
_BATCH_SIZE = 10
EMBEDDING_DIM = 1024  # 显式固定 DashScope text-embedding-v3 维度，避免依赖模型默认值漂移
_store: PGVector | None = None
_embeddings_instance = None


class GuidelineChunk(BaseModel):
    text: str
    score: float             # cosine similarity（0~1，越大越相似），与疾病混合分方向一致
    source: str | None = None    # 指南来源文档标题，便于医疗证据溯源
    metadata: dict = Field(default_factory=dict)


class DashScopeEmbeddings:
    """DashScope embeddings (sync; auto-batches at 10 per the API limit).

    查询侧与文档侧使用不同的 text_type（非对称检索）：短查询用 "query"，
    指南段落等长文档用 "document"，可获得更好的召回效果。
    """

    def __init__(self, api_key: str, model: str = "text-embedding-v3", dimension: int = EMBEDDING_DIM):
        import dashscope
        dashscope.api_key = api_key
        self.model = model
        self.dimension = dimension

    def _call(self, texts: List[str], text_type: str) -> List[List[float]]:
        if not texts:
            return []
        from dashscope import TextEmbedding
        out: List[List[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i:i + _BATCH_SIZE]
            result = TextEmbedding.call(
                model=self.model,
                input=batch,
                dimension=self.dimension,
                text_type=text_type,
            )
            if result.output and "embeddings" in result.output:
                ordered = sorted(result.output["embeddings"], key=lambda x: x["text_index"])
                out.extend(item["embedding"] for item in ordered)
            else:
                raise ValueError(f"DashScope embedding failed: {result}")
        return out

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._call(texts, "document")

    def embed_queries(self, texts: List[str]) -> List[List[float]]:
        return self._call(texts, "query")

    def embed_query(self, text: str) -> List[float]:
        return self.embed_queries([text])[0]


def get_embeddings() -> DashScopeEmbeddings:
    """获取共享的 DashScopeEmbeddings 实例。"""
    global _embeddings_instance
    if _embeddings_instance is None:
        settings = get_mcp_settings()
        _embeddings_instance = DashScopeEmbeddings(
            api_key=settings.llm_api_key, model=settings.embedding_model
        )
    return _embeddings_instance


async def embed_texts(texts: list[str], text_type: str = "document") -> list[list[float]]:
    """批量生成文本的 embedding（在线程中运行同步调用）。

    text_type: "document" 用于知识库长文档（指南等），"query" 用于短查询/症状列表。
    同一列内的向量必须使用同一 text_type，否则向量空间不一致，检索会失真。
    """
    emb = get_embeddings()
    if text_type == "query":
        return await asyncio.to_thread(emb.embed_queries, texts)
    return await asyncio.to_thread(emb.embed_documents, texts)


async def embed_query(text: str) -> list[float]:
    """生成单条文本的 embedding。"""
    emb = get_embeddings()
    return await asyncio.to_thread(emb.embed_query, text)


def _get_store() -> PGVector:
    global _store
    if _store is None:
        settings = get_mcp_settings()
        # 显式指定 COSINE，保证 similarity_search_with_score 返回的是 cosine distance (1 - similarity)
        _store = PGVector.from_existing_index(
            embedding=get_embeddings(),
            collection_name=COLLECTION_NAME,
            connection=settings.psycopg_url,
            distance_strategy=DistanceStrategy.COSINE,
            use_jsonb=True,
        )
    return _store


async def search_guidelines(query: str, k: int = 3) -> list[GuidelineChunk]:
    try:
        store = _get_store()
        pairs = await asyncio.to_thread(store.similarity_search_with_score, query, k)
        chunks = []
        for doc, dist in pairs:
            # COSINE 策略下 raw score 是 distance，转成 similarity（越大越相似）并钳制到 [0,1]
            similarity = min(1.0, max(0.0, 1.0 - float(dist)))
            md = doc.metadata or {}
            source = md.get("title") or md.get("source")
            chunks.append(GuidelineChunk(
                text=doc.page_content,
                score=round(similarity, 4),
                source=source,
                metadata=md,
            ))
        return chunks
    except Exception as e:
        logger.warning("search_guidelines failed: %s", e)
        return []
