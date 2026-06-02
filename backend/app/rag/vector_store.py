"""pgvector 向量库初始化与文档加载"""

from pathlib import Path
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.rag.embeddings import DashScopeEmbeddings

BATCH_SIZE = 10
COLLECTION_NAME = "medical_guidelines"


def _get_embeddings(settings) -> DashScopeEmbeddings:
    return DashScopeEmbeddings(
        api_key=settings.llm_api_key,
        model=settings.embedding_model,
    )


def _load_guidelines(data_dir: str) -> list[str]:
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
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", " "],
    )
    chunks = []
    for doc in documents:
        chunks.extend(splitter.split_text(doc))
    return chunks


def _get_connection_string(settings) -> str:
    """将 asyncpg 连接字符串转为 psycopg 格式"""
    return settings.database_url.replace("+asyncpg", "")


def _create_and_populate(settings) -> PGVector:
    """创建新的 pgvector 集合并填充文档"""
    embeddings = _get_embeddings(settings)
    connection_string = _get_connection_string(settings)
    documents = _load_guidelines(settings.data_dir)

    if not documents:
        raise ValueError(f"No guideline documents found in {settings.data_dir}/guidelines/")

    chunks = _split_documents(documents)
    ids = [f"doc_{i}" for i in range(len(chunks))]

    # DashScope API 限制批量大小 <= 10，需要分批处理
    vectordb = None
    for i in range(0, len(chunks), BATCH_SIZE):
        batch_texts = chunks[i:i + BATCH_SIZE]
        batch_ids = ids[i:i + BATCH_SIZE]
        if vectordb is None:
            vectordb = PGVector.from_texts(
                texts=batch_texts,
                embedding=embeddings,
                collection_name=COLLECTION_NAME,
                connection=connection_string,
                use_jsonb=True,
                ids=batch_ids,
                embedding_length=1024,
            )
        else:
            vectordb.add_texts(texts=batch_texts, ids=batch_ids)

    return vectordb


def init_vector_store_sync(settings) -> PGVector:
    """初始化 pgvector 向量库（同步版本）

    若已有数据则加载；否则从 data/guidelines/ 创建。
    """
    embeddings = _get_embeddings(settings)
    connection_string = _get_connection_string(settings)

    # 尝试加载已有索引
    try:
        vectordb = PGVector.from_existing_index(
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            connection=connection_string,
            use_jsonb=True,
        )
        # 检查是否有实际数据
        results = vectordb.similarity_search("test", k=1)
        if results:
            return vectordb
        # 集合存在但无数据，删除后重建
        vectordb.delete_collection()
    except Exception:
        pass

    return _create_and_populate(settings)


async def init_vector_store(settings) -> PGVector:
    """初始化 pgvector 向量库（异步接口，内部使用同步）"""
    return init_vector_store_sync(settings)
