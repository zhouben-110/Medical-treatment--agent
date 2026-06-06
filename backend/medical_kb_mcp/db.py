"""Postgres-backed disease queries (Dice scoring over text[] + GIN)."""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from medical_kb_mcp.config import get_mcp_settings
from medical_kb_mcp.models import Disease

_sessionmaker: async_sessionmaker[AsyncSession] | None = None


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
    user_set = set(cleaned)

    async with _get_sessionmaker()() as session:
        stmt = select(Disease).where(Disease.symptoms.overlap(cleaned))
        rows = (await session.execute(stmt)).scalars().all()

    matches: list[DiseaseMatch] = []
    for d in rows:
        dset = set(d.symptoms)
        inter = user_set & dset
        if not inter:
            continue
        score = 2 * len(inter) / (len(dset) + len(user_set))
        matches.append(DiseaseMatch(
            name=d.name,
            matched_symptoms=sorted(inter),
            match_score=round(score, 2),
            severity=d.severity,
            description=d.description,
        ))
    matches.sort(key=lambda m: (-m.match_score, -len(m.matched_symptoms)))
    return matches[:limit]


async def get_disease_detail(name: str) -> DiseaseDetail | None:
    async with _get_sessionmaker()() as session:
        d = (await session.execute(
            select(Disease).where(Disease.name == name)
        )).scalars().first()
        if d is None:
            d = (await session.execute(
                select(Disease).where(Disease.name.contains(name))
            )).scalars().first()
    if d is None:
        return None
    return DiseaseDetail(
        name=d.name, description=d.description, treatment=d.treatment,
        when_to_see_doctor=d.when_to_see_doctor, severity=d.severity,
        symptoms=list(d.symptoms),
    )
