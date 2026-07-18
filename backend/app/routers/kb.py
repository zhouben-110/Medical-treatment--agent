"""知识库管理路由 - 疾病与诊疗指南的 CRUD 及检索测试（仅管理员可访问）"""

import uuid
import logging
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kb", dependencies=[Depends(require_admin)])


# ──────────────────────── Pydantic Schemas ────────────────────────

class DiseaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    symptoms: list[str] = Field(..., min_length=1)
    description: str = ""
    treatment: str = ""
    when_to_see_doctor: str = ""
    severity: str = ""


class DiseaseUpdate(BaseModel):
    name: Optional[str] = None
    symptoms: Optional[list[str]] = None
    description: Optional[str] = None
    treatment: Optional[str] = None
    when_to_see_doctor: Optional[str] = None
    severity: Optional[str] = None


class GuidelineCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=10)


class SearchTestRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: str = "guidelines"   # "guidelines" | "diseases"
    k: int = Field(5, ge=1, le=20)


# ──────────────────────── Helper: get MCP sessionmaker ────────────────────────

def _get_kb_session():
    from medical_kb_mcp.db import _get_sessionmaker
    return _get_sessionmaker()


# ──────────────────────── Disease CRUD ────────────────────────

@router.get("/diseases")
async def list_diseases(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="按疾病名称或症状搜索"),
):
    """获取疾病列表（分页 + 搜索）"""
    from medical_kb_mcp.models import Disease
    from sqlalchemy import select, func, or_

    sm = _get_kb_session()
    async with sm() as session:
        base_q = select(Disease)
        if search.strip():
            keyword = f"%{search.strip()}%"
            base_q = base_q.where(
                or_(
                    Disease.name.ilike(keyword),
                    Disease.description.ilike(keyword),
                )
            )

        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        offset = (page - 1) * size
        rows = (
            await session.execute(
                base_q.order_by(Disease.name).offset(offset).limit(size)
            )
        ).scalars().all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": d.id,
                "name": d.name,
                "symptoms": d.symptoms,
                "description": d.description,
                "treatment": d.treatment,
                "when_to_see_doctor": d.when_to_see_doctor,
                "severity": d.severity,
                "has_embedding": d.symptom_embedding is not None,
            }
            for d in rows
        ],
    }


@router.get("/diseases/{disease_id}")
async def get_disease(disease_id: str):
    """获取单个疾病详情"""
    from medical_kb_mcp.models import Disease

    sm = _get_kb_session()
    async with sm() as session:
        d = await session.get(Disease, disease_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="疾病不存在")
    return {
        "id": d.id,
        "name": d.name,
        "symptoms": d.symptoms,
        "description": d.description,
        "treatment": d.treatment,
        "when_to_see_doctor": d.when_to_see_doctor,
        "severity": d.severity,
        "has_embedding": d.symptom_embedding is not None,
    }


@router.post("/diseases", status_code=status.HTTP_201_CREATED)
async def create_disease(body: DiseaseCreate):
    """新建疾病并自动生成 embedding"""
    from medical_kb_mcp.models import Disease
    from medical_kb_mcp.vectors import embed_query
    from sqlalchemy import select

    sm = _get_kb_session()
    async with sm() as session:
        # 检查名称唯一性
        existing = (
            await session.execute(select(Disease).where(Disease.name == body.name))
        ).scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"疾病「{body.name}」已存在",
            )

    # 生成 embedding
    try:
        symptom_text = "、".join(body.symptoms)
        embedding = await embed_query(symptom_text)
    except Exception as e:
        logger.warning(f"Embedding 生成失败，将跳过向量索引: {e}")
        embedding = None

    disease = Disease(
        id=str(uuid.uuid4()),
        name=body.name,
        symptoms=body.symptoms,
        description=body.description,
        treatment=body.treatment,
        when_to_see_doctor=body.when_to_see_doctor,
        severity=body.severity,
        symptom_embedding=embedding,
    )

    async with sm() as session:
        session.add(disease)
        await session.commit()
        await session.refresh(disease)

    return {"id": disease.id, "name": disease.name, "detail": "疾病已创建"}


@router.put("/diseases/{disease_id}")
async def update_disease(disease_id: str, body: DiseaseUpdate):
    """更新疾病信息，若症状变化则重新生成 embedding"""
    from medical_kb_mcp.models import Disease
    from medical_kb_mcp.vectors import embed_query

    sm = _get_kb_session()
    async with sm() as session:
        d = await session.get(Disease, disease_id)
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="疾病不存在")

        symptoms_changed = body.symptoms is not None and set(body.symptoms) != set(d.symptoms)

        if body.name is not None:
            d.name = body.name
        if body.symptoms is not None:
            d.symptoms = body.symptoms
        if body.description is not None:
            d.description = body.description
        if body.treatment is not None:
            d.treatment = body.treatment
        if body.when_to_see_doctor is not None:
            d.when_to_see_doctor = body.when_to_see_doctor
        if body.severity is not None:
            d.severity = body.severity

        if symptoms_changed:
            try:
                symptom_text = "、".join(d.symptoms)
                d.symptom_embedding = await embed_query(symptom_text)
            except Exception as e:
                logger.warning(f"重新生成 Embedding 失败: {e}")

        await session.commit()

    return {"id": disease_id, "detail": "更新成功"}


@router.delete("/diseases/{disease_id}")
async def delete_disease(disease_id: str):
    """删除疾病"""
    from medical_kb_mcp.models import Disease

    sm = _get_kb_session()
    async with sm() as session:
        d = await session.get(Disease, disease_id)
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="疾病不存在")
        name = d.name
        await session.delete(d)
        await session.commit()

    return {"id": disease_id, "name": name, "detail": "疾病已删除"}


# ──────────────────────── Guidelines Management ────────────────────────

@router.get("/guidelines")
async def list_guidelines(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="按内容搜索"),
):
    """列出知识库中所有指南片段（从 pgvector langchain 表查询）"""
    import asyncio
    from medical_kb_mcp.vectors import _get_store

    try:
        store = _get_store()
        # 使用同步接口，在线程中运行
        def _fetch():
            # 直接查询 langchain_pg_embedding 原始数据
            # PGVector store 内部有 _session 和 _embedding_table
            with store._make_sync_session() as session:
                from sqlalchemy import text
                # 查询 embedding collection
                col_result = session.execute(
                    text("SELECT uuid FROM langchain_pg_collection WHERE name = :name"),
                    {"name": "medical_guidelines"}
                ).fetchone()
                if not col_result:
                    return [], 0
                col_uuid = col_result[0]

                count_q = "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = :cid"
                if search.strip():
                    count_q += " AND document ILIKE :kw"
                    total = session.execute(
                        text(count_q), {"cid": col_uuid, "kw": f"%{search.strip()}%"}
                    ).scalar()
                else:
                    total = session.execute(text(count_q), {"cid": col_uuid}).scalar()

                offset = (page - 1) * size
                data_q = """
                    SELECT uuid, document, cmetadata
                    FROM langchain_pg_embedding
                    WHERE collection_id = :cid
                """
                params = {"cid": col_uuid, "limit": size, "offset": offset}
                if search.strip():
                    data_q += " AND document ILIKE :kw"
                    params["kw"] = f"%{search.strip()}%"
                data_q += " ORDER BY uuid LIMIT :limit OFFSET :offset"

                rows = session.execute(text(data_q), params).fetchall()
                return rows, total or 0

        rows, total = await asyncio.to_thread(_fetch)
        items = [
            {
                "id": str(r[0]),
                "text": r[1][:300] + ("..." if len(r[1]) > 300 else ""),
                "full_text": r[1],
                "metadata": r[2] or {},
            }
            for r in rows
        ]
        return {"total": total, "page": page, "size": size, "items": items}
    except Exception as e:
        logger.warning(f"list_guidelines 失败: {e}")
        return {"total": 0, "page": page, "size": size, "items": []}


@router.post("/guidelines", status_code=status.HTTP_201_CREATED)
async def add_guideline(body: GuidelineCreate):
    """新增诊疗指南条目（自动切片并写入 pgvector）"""
    import asyncio
    from medical_kb_mcp.vectors import _get_store, get_embeddings
    from langchain_core.documents import Document

    try:
        store = _get_store()
        # 将长文本切分为 段落
        paragraphs = [p.strip() for p in body.content.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [body.content.strip()]

        docs = [
            Document(
                page_content=f"来自《{body.title}》：{para}",
                metadata={"title": body.title, "source": "admin_upload"},
            )
            for para in paragraphs
        ]

        def _add():
            store.add_documents(docs)

        await asyncio.to_thread(_add)
        return {"detail": f"已成功写入 {len(docs)} 个指南片段", "chunks": len(docs)}
    except Exception as e:
        logger.error(f"add_guideline 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"写入失败: {str(e)}",
        )


@router.delete("/guidelines/{chunk_id}")
async def delete_guideline(chunk_id: str):
    """删除指定指南片段"""
    import asyncio
    from medical_kb_mcp.vectors import _get_store

    try:
        store = _get_store()

        def _delete():
            store.delete([chunk_id])

        await asyncio.to_thread(_delete)
        return {"id": chunk_id, "detail": "片段已删除"}
    except Exception as e:
        logger.error(f"delete_guideline 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}",
        )


# ──────────────────────── Stats ────────────────────────

@router.get("/stats")
async def get_kb_stats():
    """知识库总览统计"""
    import asyncio
    from medical_kb_mcp.models import Disease
    from medical_kb_mcp.vectors import _get_store
    from sqlalchemy import select, func

    sm = _get_kb_session()
    async with sm() as session:
        disease_count = (await session.execute(select(func.count()).select_from(Disease))).scalar() or 0
        embedded_count = (
            await session.execute(
                select(func.count()).select_from(Disease).where(Disease.symptom_embedding.isnot(None))
            )
        ).scalar() or 0

    guideline_count = 0
    try:
        store = _get_store()

        def _count():
            with store._make_sync_session() as s:
                from sqlalchemy import text
                col = s.execute(
                    text("SELECT uuid FROM langchain_pg_collection WHERE name = :name"),
                    {"name": "medical_guidelines"},
                ).fetchone()
                if not col:
                    return 0
                return s.execute(
                    text("SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = :cid"),
                    {"cid": col[0]},
                ).scalar() or 0

        guideline_count = await asyncio.to_thread(_count)
    except Exception as e:
        logger.warning(f"stats guideline count 失败: {e}")

    return {
        "disease_count": disease_count,
        "embedded_count": embedded_count,
        "guideline_chunk_count": guideline_count,
    }


# ──────────────────────── RAG Search Test ────────────────────────

@router.post("/search/test")
async def test_search(body: SearchTestRequest):
    """在管理后台直接测试 RAG 检索效果"""
    if body.mode == "guidelines":
        from medical_kb_mcp.vectors import search_guidelines
        results = await search_guidelines(body.query, body.k)
        return {
            "mode": "guidelines",
            "query": body.query,
            "results": [{"text": r.text, "score": r.score} for r in results],
        }
    elif body.mode == "diseases":
        from medical_kb_mcp.db import search_diseases_by_symptoms
        symptoms = [s.strip() for s in body.query.split() if s.strip()]
        if not symptoms:
            symptoms = [body.query]
        results = await search_diseases_by_symptoms(symptoms, body.k)
        return {
            "mode": "diseases",
            "query": body.query,
            "results": [
                {
                    "name": r.name,
                    "score": r.match_score,
                    "severity": r.severity,
                    "matched_symptoms": r.matched_symptoms,
                }
                for r in results
            ],
        }
    else:
        raise HTTPException(status_code=400, detail="mode 必须为 guidelines 或 diseases")
