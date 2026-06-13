"""Postgres-backed disease queries (embedding cosine similarity via pgvector)."""

import logging
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from medical_kb_mcp.config import get_mcp_settings
from medical_kb_mcp.models import Disease

logger = logging.getLogger(__name__)

_sessionmaker: async_sessionmaker[AsyncSession] | None = None

SIMILARITY_THRESHOLD = 0.3  # cosine 相似度低于此值的结果不返回


class DiseaseMatch(BaseModel):
    name: str
    matched_symptoms: list[str]
    match_score: float
    severity: str
    description: str


class DiseaseDetail(BaseModel):
    name: str
    description: str
    treatment: str
    when_to_see_doctor: str
    severity: str
    symptoms: list[str]


def set_sessionmaker(sm) -> None:
    """Override the sessionmaker (used by tests)."""
    global _sessionmaker
    _sessionmaker = sm


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        engine = create_async_engine(get_mcp_settings().database_url)
        _sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return _sessionmaker


async def search_diseases_by_symptoms(symptoms: list[str], limit: int = 5) -> list[DiseaseMatch]:
    cleaned = [s.strip() for s in symptoms if s and s.strip()]
    if not cleaned:
        return []

    from medical_kb_mcp.vectors import embed_query

    query_text = "、".join(cleaned)
    query_embedding = await embed_query(query_text)
    user_set = set(cleaned)

    async with _get_sessionmaker()() as session:
        # 只查有 embedding 的疾病，按 cosine 距离排序
        distance = Disease.symptom_embedding.cosine_distance(query_embedding)
        stmt = (
            select(Disease, distance.label("dist"))
            .where(Disease.symptom_embedding.isnot(None))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

    matches: list[DiseaseMatch] = []
    for d, dist in rows:
        similarity = 1 - dist
        if similarity < SIMILARITY_THRESHOLD:
            continue
        # 保留交集信息作为辅助参考
        dset = set(d.symptoms)
        inter = user_set & dset
        matches.append(DiseaseMatch(
            name=d.name,
            matched_symptoms=sorted(inter),
            match_score=round(similarity, 2),
            severity=d.severity,
            description=d.description,
        ))

    return matches


async def get_disease_detail(name: str) -> DiseaseDetail | None:
    async with _get_sessionmaker()() as session:
        d = (await session.execute(
            select(Disease).where(Disease.name == name)
        )).scalars().first()
        if d is None:
            d = (await session.execute(
                select(Disease).where(Disease.name.contains(name)).order_by(Disease.name)
            )).scalars().first()
    if d is None:
        return None
    return DiseaseDetail(
        name=d.name, description=d.description, treatment=d.treatment,
        when_to_see_doctor=d.when_to_see_doctor, severity=d.severity,
        symptoms=list(d.symptoms),
    )
