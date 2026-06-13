"""pgvector + DashScope guideline retrieval (moved out of app/rag)."""

import asyncio
import logging
from typing import List
from pydantic import BaseModel
from langchain_postgres import PGVector
from medical_kb_mcp.config import get_mcp_settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "medical_guidelines"
_BATCH_SIZE = 10
_store: PGVector | None = None
_embeddings_instance = None


class GuidelineChunk(BaseModel):
    text: str
    score: float


class DashScopeEmbeddings:
    """DashScope embeddings (sync; auto-batches at 10 per the API limit)."""

    def __init__(self, api_key: str, model: str = "text-embedding-v3"):
        import dashscope
        dashscope.api_key = api_key
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        from dashscope import TextEmbedding
        out: List[List[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i:i + _BATCH_SIZE]
            result = TextEmbedding.call(model=self.model, input=batch)
            if result.output and "embeddings" in result.output:
                ordered = sorted(result.output["embeddings"], key=lambda x: x["text_index"])
                out.extend(item["embedding"] for item in ordered)
            else:
                raise ValueError(f"DashScope embedding failed: {result}")
        return out

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


def get_embeddings() -> DashScopeEmbeddings:
    """获取共享的 DashScopeEmbeddings 实例。"""
    global _embeddings_instance
    if _embeddings_instance is None:
        settings = get_mcp_settings()
        _embeddings_instance = DashScopeEmbeddings(
            api_key=settings.llm_api_key, model=settings.embedding_model
        )
    return _embeddings_instance


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量生成文本的 embedding（在线程中运行同步调用）。"""
    emb = get_embeddings()
    return await asyncio.to_thread(emb.embed_documents, texts)


async def embed_query(text: str) -> list[float]:
    """生成单条文本的 embedding。"""
    emb = get_embeddings()
    return await asyncio.to_thread(emb.embed_query, text)


def _get_store() -> PGVector:
    global _store
    if _store is None:
        settings = get_mcp_settings()
        _store = PGVector.from_existing_index(
            embedding=get_embeddings(),
            collection_name=COLLECTION_NAME,
            connection=settings.psycopg_url,
            use_jsonb=True,
        )
    return _store


async def search_guidelines(query: str, k: int = 3) -> list[GuidelineChunk]:
    try:
        store = _get_store()
        pairs = await asyncio.to_thread(store.similarity_search_with_score, query, k)
        return [GuidelineChunk(text=doc.page_content, score=float(score)) for doc, score in pairs]
    except Exception as e:
        logger.warning("search_guidelines failed: %s", e)
        return []
