"""Chroma 向量库初始化与文档加载"""

import os
from pathlib import Path
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.rag.embeddings import DashScopeEmbeddings

# DashScope API 批量限制
BATCH_SIZE = 10


def _get_embeddings(settings) -> DashScopeEmbeddings:
    """创建 DashScope 嵌入模型实例"""
    return DashScopeEmbeddings(
        api_key=settings.llm_api_key,
        model=settings.embedding_model,
    )


def _load_guidelines(data_dir: str) -> list[str]:
    """扫描 data/guidelines/ 目录，加载所有 .md 文件内容"""
    guidelines_path = Path(data_dir) / "guidelines"
    if not guidelines_path.exists():
        return []

    documents = []
    for md_file in guidelines_path.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        if content.strip():
            documents.append(content)
    return documents


def _split_documents(documents: list[str]) -> list[str]:
    """将文档按段落分 chunk"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", " "],
    )
    chunks = []
    for doc in documents:
        chunks.extend(splitter.split_text(doc))
    return chunks


async def init_vector_store(settings) -> Chroma:
    """初始化 Chroma 向量库

    若持久化目录已存在且有数据，直接加载；
    否则从 data/guidelines/ 加载文档并创建。
    """
    embeddings = _get_embeddings(settings)
    persist_dir = settings.chroma_persist_dir

    # 检查是否已有持久化数据
    if os.path.exists(persist_dir) and os.listdir(persist_dir):
        vectordb = Chroma(
            persist_directory=persist_dir,
            embedding_function=embeddings,
            collection_name="medical_guidelines",
        )
        if vectordb._collection.count() > 0:
            return vectordb

    # 加载文档并分 chunk
    documents = _load_guidelines(settings.data_dir)

    # 创建空集合
    vectordb = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings,
        collection_name="medical_guidelines",
    )

    if documents:
        chunks = _split_documents(documents)
        # 分批添加（DashScope API 限制批量大小 <= 10）
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            vectordb.add_texts(texts=batch)

    return vectordb
