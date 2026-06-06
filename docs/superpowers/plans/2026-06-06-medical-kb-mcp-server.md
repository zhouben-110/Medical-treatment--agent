# Medical-KB MCP Server Implementation Plan (M1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the medical knowledge layer into a standalone Medical-KB MCP Server (3 atomic tools, stdio + Streamable HTTP), migrate the hardcoded disease table into Postgres, and have the LangGraph agent consume it via `langchain-mcp-adapters`.

**Architecture:** New `backend/medical_kb_mcp/` package owns disease queries (Postgres `text[]` + GIN, Dice scoring) and guideline vector search (pgvector + DashScope). It runs as an independent process exposing `search_diseases_by_symptoms`, `get_disease_detail`, `search_guidelines`. The FastAPI app keeps only a thin `mcp_client.py` + slimmed `retriever.py`; the old `app/rag/{knowledge_base,vector_store,embeddings}.py` logic moves out. M1 keeps the existing graph nodes calling the retriever programmatically — LLM-driven tool selection is deferred to M2.

**Tech Stack:** Python 3.10+, `mcp` (FastMCP), `langchain-mcp-adapters`, SQLAlchemy 2.x async + asyncpg, `langchain-postgres` (PGVector), DashScope embeddings, Alembic, pytest + pytest-asyncio.

**Source spec:** `docs/superpowers/specs/2026-06-06-medical-kb-mcp-server-design.md`

**Preconditions:**
- A running Postgres with the `pgvector` extension (same instance the app uses). The existing tests already require Postgres.
- The design spec should already be committed. If the working tree still shows it uncommitted (bash was unavailable during design), include it in the Task 1 commit.

**API version note (verify against installed versions):** `langchain-mcp-adapters` accepts `"transport": "streamable_http"` (older/SDK-aligned) or `"http"` (newer docs) — this plan uses `"streamable_http"`. FastMCP is imported as `from mcp.server.fastmcp import FastMCP`; HTTP transport string is `"streamable-http"`.

---

### Task 1: Dependencies + package skeleton + config

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/medical_kb_mcp/__init__.py`
- Create: `backend/medical_kb_mcp/config.py`
- Test: `backend/tests/test_mcp_config.py`

- [ ] **Step 1: Add dependencies**

In `backend/requirements.txt` append:

```
mcp>=1.9.0
langchain-mcp-adapters>=0.1.0
dashscope>=1.20.0
```

(`dashscope` is currently imported by `app/rag/embeddings.py` but missing from requirements — this makes it explicit before the logic moves.)

- [ ] **Step 2: Install**

Run: `pip install -r backend/requirements.txt`
Expected: installs `mcp`, `langchain-mcp-adapters`, `dashscope` with no resolver errors.

- [ ] **Step 3: Create the package init**

`backend/medical_kb_mcp/__init__.py`:

```python
"""Medical-KB MCP Server: standalone medical knowledge service."""
```

- [ ] **Step 4: Write the failing test for config**

`backend/tests/test_mcp_config.py`:

```python
import os


def test_mcp_settings_reads_env(monkeypatch):
    monkeypatch.setenv("MCP_PORT", "9001")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/x")
    from medical_kb_mcp.config import MCPSettings
    s = MCPSettings()
    assert s.mcp_port == 9001
    assert s.database_url.endswith("/x")
    assert s.embedding_model  # has a default
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mcp_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'medical_kb_mcp.config'`

- [ ] **Step 6: Implement config**

`backend/medical_kb_mcp/config.py`:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings


class MCPSettings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medical_agent"
    llm_api_key: str = ""              # DashScope API key (same .env var the app uses)
    embedding_model: str = "text-embedding-v3"
    data_dir: str = "./data"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def psycopg_url(self) -> str:
        """psycopg (sync) connection string for PGVector."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache()
def get_mcp_settings() -> MCPSettings:
    return MCPSettings()
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && pytest tests/test_mcp_config.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/medical_kb_mcp/__init__.py backend/medical_kb_mcp/config.py backend/tests/test_mcp_config.py docs/superpowers/specs/2026-06-06-medical-kb-mcp-server-design.md
git commit -m "feat(mcp): add medical_kb_mcp package skeleton, config, deps"
```

---

### Task 2: Disease ORM model + Alembic migration

**Files:**
- Create: `backend/medical_kb_mcp/models.py`
- Create: `backend/alembic/versions/m1diseases001_add_diseases_table.py`
- Modify: `backend/alembic/env.py:9-17`
- Test: `backend/tests/test_mcp_models.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_mcp_models.py`:

```python
def test_disease_table_shape():
    from medical_kb_mcp.models import Disease, Base
    t = Base.metadata.tables["diseases"]
    cols = set(t.columns.keys())
    assert {"id", "name", "symptoms", "description",
            "treatment", "when_to_see_doctor", "severity"} <= cols
    # GIN index on symptoms is declared
    idx_names = {i.name for i in t.indexes}
    assert "ix_diseases_symptoms_gin" in idx_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mcp_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'medical_kb_mcp.models'`

- [ ] **Step 3: Implement the model**

`backend/medical_kb_mcp/models.py`:

```python
import uuid
from sqlalchemy import String, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _gen_id() -> str:
    return str(uuid.uuid4())


class Disease(Base):
    __tablename__ = "diseases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_gen_id)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    symptoms: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    treatment: Mapped[str] = mapped_column(Text, default="")
    when_to_see_doctor: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String, default="")

    __table_args__ = (
        Index("ix_diseases_symptoms_gin", "symptoms", postgresql_using="gin"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_mcp_models.py -v`
Expected: PASS

- [ ] **Step 5: Write the Alembic migration**

`backend/alembic/versions/m1diseases001_add_diseases_table.py`:

```python
"""add diseases table

Revision ID: m1diseases001
Revises: d888745e3d0c
Create Date: 2026-06-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "m1diseases001"
down_revision: Union[str, Sequence[str], None] = "d888745e3d0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diseases",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("symptoms", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("treatment", sa.Text(), nullable=True),
        sa.Column("when_to_see_doctor", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_diseases_symptoms_gin", "diseases", ["symptoms"],
        unique=False, postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_diseases_symptoms_gin", table_name="diseases")
    op.drop_table("diseases")
```

- [ ] **Step 6: Register the MCP metadata in Alembic env**

In `backend/alembic/env.py`, change lines 9 and 17. Replace:

```python
from app.models import Base
```

with:

```python
from app.models import Base
from medical_kb_mcp.models import Base as MCPBase
```

and replace:

```python
target_metadata = Base.metadata
```

with:

```python
target_metadata = [Base.metadata, MCPBase.metadata]
```

(Prevents a future `--autogenerate` from trying to drop `diseases`.)

- [ ] **Step 7: Apply the migration**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade d888745e3d0c -> m1diseases001, add diseases table`. Verify in psql: `\d diseases` shows the `symptoms` column as `text[]` and a `gin` index.

- [ ] **Step 8: Commit**

```bash
git add backend/medical_kb_mcp/models.py backend/alembic/versions/m1diseases001_add_diseases_table.py backend/alembic/env.py backend/tests/test_mcp_models.py
git commit -m "feat(mcp): add diseases table model + alembic migration (text[] + GIN)"
```

---

### Task 3: Disease queries — Dice match + detail lookup

**Files:**
- Create: `backend/medical_kb_mcp/db.py`
- Test: `backend/tests/test_mcp_db.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_mcp_db.py`:

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medical_kb_mcp import db as mcp_db
from medical_kb_mcp.models import Base, Disease
from medical_kb_mcp.config import get_mcp_settings


@pytest_asyncio.fixture
async def seeded_db():
    engine = create_async_engine(get_mcp_settings().database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        s.add_all([
            Disease(name="普通感冒", symptoms=["发热", "咳嗽", "流涕", "咽痛"],
                    description="上呼吸道感染", treatment="对症", when_to_see_doctor="高热不退", severity="轻"),
            Disease(name="流行性感冒", symptoms=["发热", "乏力", "肌肉酸痛", "咳嗽"],
                    description="流感病毒", treatment="奥司他韦", when_to_see_doctor="呼吸困难", severity="中"),
        ])
        await s.commit()
    mcp_db.set_sessionmaker(sm)         # inject test sessionmaker
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    mcp_db.set_sessionmaker(None)


@pytest.mark.asyncio
async def test_search_ranks_by_dice(seeded_db):
    res = await mcp_db.search_diseases_by_symptoms(["发热", "咳嗽", "流涕", "咽痛"])
    assert res[0].name == "普通感冒"          # exact 4/4 overlap wins
    assert res[0].match_score == 1.0
    assert set(res[0].matched_symptoms) == {"发热", "咳嗽", "流涕", "咽痛"}


@pytest.mark.asyncio
async def test_search_empty_returns_empty(seeded_db):
    assert await mcp_db.search_diseases_by_symptoms([]) == []


@pytest.mark.asyncio
async def test_get_detail_exact_and_contains(seeded_db):
    d = await mcp_db.get_disease_detail("普通感冒")
    assert d is not None and d.treatment == "对症"
    assert await mcp_db.get_disease_detail("不存在的病") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mcp_db.py -v`
Expected: FAIL with `AttributeError: module 'medical_kb_mcp.db' has no attribute 'set_sessionmaker'`

- [ ] **Step 3: Implement db.py**

`backend/medical_kb_mcp/db.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_mcp_db.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/medical_kb_mcp/db.py backend/tests/test_mcp_db.py
git commit -m "feat(mcp): disease search (Dice over text[]) + detail lookup"
```

---

### Task 4: Seed the 25 diseases into Postgres

**Files:**
- Create: `backend/medical_kb_mcp/seed_diseases.py`
- Test: `backend/tests/test_mcp_seed.py`

- [ ] **Step 1: Build the seed data + script**

Copy the `DISEASE_KNOWLEDGE` list **verbatim** from `backend/app/rag/knowledge_base.py:3-204` into the top of `seed_diseases.py` (it is still present at this point; Task 8 deletes the original). Then add the idempotent seeding logic. The source dicts use key `"disease"` → map to model field `name`; all other keys (`symptoms`, `description`, `treatment`, `when_to_see_doctor`, `severity`) map 1:1.

`backend/medical_kb_mcp/seed_diseases.py`:

```python
"""Seed the diseases table from the curated knowledge list (idempotent)."""

import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from medical_kb_mcp.config import get_mcp_settings
from medical_kb_mcp.models import Disease

# --- paste DISEASE_KNOWLEDGE (25 entries) copied verbatim from
#     backend/app/rag/knowledge_base.py:3-204 here ---
DISEASE_KNOWLEDGE = [
    # {"disease": "...", "symptoms": [...], "description": "...",
    #  "treatment": "...", "when_to_see_doctor": "...", "severity": "..."},
    # ... 25 entries ...
]


async def seed(sessionmaker=None) -> int:
    if sessionmaker is None:
        engine = create_async_engine(get_mcp_settings().database_url)
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    inserted = 0
    async with sessionmaker() as session:
        for entry in DISEASE_KNOWLEDGE:
            exists = (await session.execute(
                select(func.count()).select_from(Disease).where(Disease.name == entry["disease"])
            )).scalar_one()
            if exists:
                continue
            session.add(Disease(
                name=entry["disease"],
                symptoms=entry["symptoms"],
                description=entry["description"],
                treatment=entry["treatment"],
                when_to_see_doctor=entry["when_to_see_doctor"],
                severity=entry["severity"],
            ))
            inserted += 1
        await session.commit()
    return inserted


if __name__ == "__main__":
    n = asyncio.run(seed())
    print(f"Seeded {n} new diseases.")
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_mcp_seed.py`:

```python
import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medical_kb_mcp import seed_diseases
from medical_kb_mcp.models import Base, Disease
from medical_kb_mcp.config import get_mcp_settings


@pytest_asyncio.fixture
async def empty_db():
    engine = create_async_engine(get_mcp_settings().database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_is_idempotent(empty_db):
    first = await seed_diseases.seed(empty_db)
    assert first == 25
    second = await seed_diseases.seed(empty_db)   # re-run inserts nothing
    assert second == 0
    async with empty_db() as s:
        total = (await s.execute(select(func.count()).select_from(Disease))).scalar_one()
    assert total == 25
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mcp_seed.py -v`
Expected: FAIL — `assert first == 25` fails because `DISEASE_KNOWLEDGE` is still the empty placeholder. (This confirms you must paste the 25 entries in Step 1.)

- [ ] **Step 4: Paste the data and re-run**

After pasting all 25 entries from `knowledge_base.py:3-204`:
Run: `cd backend && pytest tests/test_mcp_seed.py -v`
Expected: PASS

- [ ] **Step 5: Seed the real database**

Run: `cd backend && python -m medical_kb_mcp.seed_diseases`
Expected: `Seeded 25 new diseases.`

- [ ] **Step 6: Commit**

```bash
git add backend/medical_kb_mcp/seed_diseases.py backend/tests/test_mcp_seed.py
git commit -m "feat(mcp): seed 25 diseases into Postgres (idempotent)"
```

---

### Task 5: Guideline vector search (pgvector + DashScope)

**Files:**
- Create: `backend/medical_kb_mcp/vectors.py`
- Test: `backend/tests/test_mcp_vectors.py`

- [ ] **Step 1: Write the failing test (mocked vector store, no network)**

`backend/tests/test_mcp_vectors.py`:

```python
import pytest
from unittest.mock import MagicMock
from langchain_core.documents import Document

from medical_kb_mcp import vectors


@pytest.mark.asyncio
async def test_search_guidelines_maps_chunks(monkeypatch):
    fake_store = MagicMock()
    fake_store.similarity_search_with_score.return_value = [
        (Document(page_content="感冒应多休息多饮水"), 0.12),
        (Document(page_content="高热不退应就医"), 0.34),
    ]
    monkeypatch.setattr(vectors, "_get_store", lambda: fake_store)

    res = await vectors.search_guidelines("感冒 治疗", k=2)
    assert [c.text for c in res] == ["感冒应多休息多饮水", "高热不退应就医"]
    assert res[0].score == 0.12


@pytest.mark.asyncio
async def test_search_guidelines_degrades_on_error(monkeypatch):
    def boom():
        raise RuntimeError("pgvector down")
    monkeypatch.setattr(vectors, "_get_store", boom)
    assert await vectors.search_guidelines("x") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mcp_vectors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'medical_kb_mcp.vectors'`

- [ ] **Step 3: Implement vectors.py**

Move `DashScopeEmbeddings` here (copy from `backend/app/rag/embeddings.py:9-40`) and adapt the PGVector load from `backend/app/rag/vector_store.py`. `backend/medical_kb_mcp/vectors.py`:

```python
"""pgvector + DashScope guideline retrieval (moved out of app/rag)."""

import asyncio
from typing import List
from pydantic import BaseModel
from langchain_postgres import PGVector
from medical_kb_mcp.config import get_mcp_settings

COLLECTION_NAME = "medical_guidelines"
_BATCH_SIZE = 10
_store: PGVector | None = None


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


def _get_store() -> PGVector:
    global _store
    if _store is None:
        settings = get_mcp_settings()
        _store = PGVector.from_existing_index(
            embedding=DashScopeEmbeddings(api_key=settings.llm_api_key, model=settings.embedding_model),
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
    except Exception as e:  # graceful degradation — never crash the tool
        print(f"[mcp.vectors] search_guidelines failed: {e}")
        return []
```

> **Ingestion is out of scope for M1.** `search_guidelines` reads the **existing** `medical_guidelines` pgvector collection via `from_existing_index` — that collection is already populated by the prior system, so no ingestion code is needed here. If the collection is missing (e.g. a fresh database), `from_existing_index`/search raises and `search_guidelines` degrades to `[]` (structured disease search still works). Re-ingesting `data/guidelines/*.md` into a fresh DB is a documented follow-up, not part of M1.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_mcp_vectors.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/medical_kb_mcp/vectors.py backend/tests/test_mcp_vectors.py
git commit -m "feat(mcp): guideline vector search + ingestion (pgvector + DashScope)"
```

---

### Task 6: FastMCP server — 3 atomic tools, dual transport

**Files:**
- Create: `backend/medical_kb_mcp/server.py`
- Test: `backend/tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test (protocol-level, mocked backends)**

`backend/tests/test_mcp_server.py`:

```python
import json
import pytest
from medical_kb_mcp import server as srv
from medical_kb_mcp.db import DiseaseMatch, DiseaseDetail
from medical_kb_mcp.vectors import GuidelineChunk


@pytest.mark.asyncio
async def test_lists_three_tools():
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    assert {"search_diseases_by_symptoms", "get_disease_detail", "search_guidelines"} <= names


@pytest.mark.asyncio
async def test_call_search_tool(monkeypatch):
    async def fake_search(symptoms, limit=5):
        return [DiseaseMatch(name="普通感冒", matched_symptoms=["发热"],
                             match_score=0.5, severity="轻", description="d")]
    monkeypatch.setattr(srv, "search_diseases_by_symptoms", fake_search)

    result = await srv.mcp.call_tool("search_diseases_by_symptoms", {"symptoms": ["发热"]})
    # FastMCP returns (content_blocks, structured_dict); assert the disease name appears
    assert "普通感冒" in json.dumps(result, default=str, ensure_ascii=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mcp_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'medical_kb_mcp.server'`

- [ ] **Step 3: Implement server.py**

`backend/medical_kb_mcp/server.py`:

```python
"""Medical-KB MCP Server. Run: python -m medical_kb_mcp.server [stdio|http]."""

import sys
from mcp.server.fastmcp import FastMCP
from medical_kb_mcp.config import get_mcp_settings
from medical_kb_mcp.db import (
    search_diseases_by_symptoms, get_disease_detail, DiseaseMatch, DiseaseDetail,
)
from medical_kb_mcp.vectors import search_guidelines, GuidelineChunk

_settings = get_mcp_settings()
mcp = FastMCP(name="medical-kb", host=_settings.mcp_host, port=_settings.mcp_port)


@mcp.tool()
async def search_diseases_by_symptoms_tool(symptoms: list[str], limit: int = 5) -> list[DiseaseMatch]:
    """根据症状列表匹配可能的疾病，按 Dice 相似度排序返回。"""
    return await search_diseases_by_symptoms(symptoms, limit)


@mcp.tool()
async def get_disease_detail_tool(name: str) -> DiseaseDetail | None:
    """按疾病名精确查找详情（描述、治疗、就医指征、严重程度、典型症状）。"""
    return await get_disease_detail(name)


@mcp.tool()
async def search_guidelines_tool(query: str, k: int = 3) -> list[GuidelineChunk]:
    """在诊疗指南向量库中按语义检索相关片段。"""
    return await search_guidelines(query, k)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if mode == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

> **Tool naming:** the test expects tool names without the `_tool` suffix. Set the public name explicitly via the decorator: change each to `@mcp.tool(name="search_diseases_by_symptoms")`, `@mcp.tool(name="get_disease_detail")`, `@mcp.tool(name="search_guidelines")`. Keep the Python function names suffixed with `_tool` to avoid colliding with the imported backend functions.

- [ ] **Step 4: Apply the explicit tool names**

Update the three decorators to `@mcp.tool(name="...")` as noted above so `list_tools()` reports the clean names.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_mcp_server.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Smoke-test both transports manually**

Run: `cd backend && python -m medical_kb_mcp.server http`
Expected: a uvicorn server starts on `127.0.0.1:8765` (endpoint `/mcp`). Ctrl-C to stop.
Run: `cd backend && python -m medical_kb_mcp.server stdio`
Expected: process waits on stdin (no crash). Ctrl-C to stop.

- [ ] **Step 7: Commit**

```bash
git add backend/medical_kb_mcp/server.py backend/tests/test_mcp_server.py
git commit -m "feat(mcp): FastMCP server exposing 3 atomic tools over stdio + http"
```

---

### Task 7: App-side MCP client

**Files:**
- Modify: `backend/app/config.py:16` (add `mcp_server_url`)
- Create: `backend/app/mcp_client.py`
- Test: `backend/tests/test_app_mcp_client.py`

- [ ] **Step 1: Add the MCP URL setting**

In `backend/app/config.py`, add inside `Settings` (e.g. after `sql_echo`):

```python
    mcp_server_url: str = "http://localhost:8765/mcp"
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_app_mcp_client.py`:

```python
import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")

import pytest
from unittest.mock import AsyncMock, patch
from app import mcp_client


@pytest.mark.asyncio
async def test_get_tool_returns_by_name():
    tool_a = type("T", (), {"name": "search_guidelines"})()
    tool_b = type("T", (), {"name": "get_disease_detail"})()
    with patch.object(mcp_client, "_load_tools", AsyncMock(return_value=[tool_a, tool_b])):
        tools = await mcp_client.load_tools()
        assert mcp_client.get_tool(tools, "get_disease_detail") is tool_b
        assert mcp_client.get_tool(tools, "nope") is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_app_mcp_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.mcp_client'`

- [ ] **Step 4: Implement mcp_client.py**

`backend/app/mcp_client.py`:

```python
"""Thin MCP client: connects the app to the Medical-KB MCP server."""

from langchain_mcp_adapters.client import MultiServerMCPClient
from app.config import get_settings


async def _load_tools() -> list:
    settings = get_settings()
    client = MultiServerMCPClient({
        "medical_kb": {"transport": "streamable_http", "url": settings.mcp_server_url},
    })
    return await client.get_tools()


async def load_tools() -> list:
    """Return the MCP tools, or [] if the server is unreachable (graceful degrade)."""
    try:
        return await _load_tools()
    except Exception as e:
        print(f"[mcp_client] could not load MCP tools: {e}")
        return []


def get_tool(tools: list, name: str):
    for t in tools:
        if getattr(t, "name", None) == name:
            return t
    return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_app_mcp_client.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/mcp_client.py backend/tests/test_app_mcp_client.py
git commit -m "feat(app): MCP client (langchain-mcp-adapters) with graceful degradation"
```

---

### Task 8: Slim the retriever, delete old rag modules, rewire lifespan

**Files:**
- Rewrite: `backend/app/rag/retriever.py`
- Delete: `backend/app/rag/knowledge_base.py`, `backend/app/rag/vector_store.py`, `backend/app/rag/embeddings.py`
- Modify: `backend/app/main.py:22-41` (lifespan)
- Test: `backend/tests/test_retriever_mcp.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_retriever_mcp.py`:

```python
import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")

import json
import pytest
from unittest.mock import AsyncMock
from app.rag.retriever import MedicalRetriever


def _tool(name, payload):
    t = type("T", (), {})()
    t.name = name
    t.ainvoke = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))
    return t


@pytest.mark.asyncio
async def test_retrieve_for_diagnosis_formats_context():
    tools = [
        _tool("search_diseases_by_symptoms",
              [{"name": "普通感冒", "matched_symptoms": ["发热"], "match_score": 0.8,
                "severity": "轻", "description": "上感"}]),
        _tool("search_guidelines", [{"text": "多休息多饮水", "score": 0.1}]),
    ]
    r = MedicalRetriever(tools)
    ctx = await r.retrieve_for_diagnosis(["发热"])
    assert "普通感冒" in ctx
    assert "多休息多饮水" in ctx


@pytest.mark.asyncio
async def test_retrieve_degrades_when_tool_missing():
    r = MedicalRetriever([])           # no tools available (server down)
    assert await r.retrieve_for_diagnosis(["发热"]) == ""
    assert await r.retrieve_for_advice(["普通感冒"], ["发热"]) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_retriever_mcp.py -v`
Expected: FAIL — current `MedicalRetriever.__init__` takes a `vector_store`, not a tool list, and calls structured-KB functions directly.

- [ ] **Step 3: Rewrite retriever.py to orchestrate MCP tools**

`backend/app/rag/retriever.py`:

```python
"""Client-side orchestrator: calls atomic MCP tools, assembles medical_context."""

import json
from app.mcp_client import get_tool


class MedicalRetriever:
    """Builds prompt context by composing the Medical-KB MCP tools."""

    def __init__(self, tools: list):
        self.tools = tools or []

    async def _call(self, name: str, args: dict):
        tool = get_tool(self.tools, name)
        if tool is None:
            return None
        try:
            raw = await tool.ainvoke(args)
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            print(f"[retriever] tool {name} failed: {e}")
            return None

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
            detail = await self._call("get_disease_detail", {"name": name})
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_retriever_mcp.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Delete the migrated modules**

```bash
git rm backend/app/rag/knowledge_base.py backend/app/rag/vector_store.py backend/app/rag/embeddings.py
```

- [ ] **Step 6: Rewire the lifespan in main.py**

In `backend/app/main.py`, replace the RAG init block (lines 22-41, the `from app.rag.vector_store import ...` / `MedicalRetriever(vector_store...)` section) with MCP-based wiring. The new lifespan body:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()

    from app.mcp_client import load_tools
    from app.rag.retriever import MedicalRetriever
    from app.nodes import disease_matcher, advisor

    try:
        tools = await load_tools()
        retriever = MedicalRetriever(tools)
        disease_matcher.retriever = retriever
        advisor.retriever = retriever
    except Exception as e:
        print(f"Warning: MCP retriever init failed, running without RAG: {e}")

    async with AsyncExitStack() as stack:
        conn_str = settings.database_url.replace("+asyncpg", "")
        saver = await stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(conn_str)
        )
        await saver.setup()
        graph_module.medical_graph = graph_module.build_graph().compile(checkpointer=saver)
        yield
```

(`disease_matcher` and `advisor` are unchanged — they still call `retriever.retrieve_for_diagnosis/advice`, now MCP-backed.)

- [ ] **Step 7: Run the full suite to confirm no regression**

Run: `cd backend && pytest -v`
Expected: all existing tests (`test_api.py`, `test_integration.py`) PASS, plus the new MCP tests. The chat tests mock `app.graph.medical_graph`, so they are unaffected by the retriever change.

- [ ] **Step 8: Commit**

```bash
git add backend/app/rag/retriever.py backend/app/main.py backend/tests/test_retriever_mcp.py
git commit -m "refactor(app): retriever consumes MCP tools; remove in-process rag modules"
```

---

### Task 9: Verification, Claude Desktop demo config, run docs

**Files:**
- Create: `backend/medical_kb_mcp/README.md`
- Create: `claude_desktop_config.example.json` (repo root)

- [ ] **Step 1: End-to-end manual verification**

1. Ensure migration applied + seeded (Tasks 2,4 done).
2. Start the MCP server (HTTP): `cd backend && python -m medical_kb_mcp.server http`
3. Start the app: `cd backend && uvicorn app.main:app --reload`
4. `curl http://localhost:8000/health` → `status` not `degraded`.
5. `curl -X POST http://localhost:8000/api/chat -H 'Content-Type: application/json' -d '{"message":"我发热咳嗽流涕三天了"}'` → reply references plausible diseases; `symptoms` populated.
6. Stop the MCP server, repeat step 5 → app still replies (degraded, no RAG context), confirming graceful degradation.

- [ ] **Step 2: Write the Claude Desktop demo config**

`claude_desktop_config.example.json` (repo root):

```json
{
  "mcpServers": {
    "medical-kb": {
      "command": "python",
      "args": ["-m", "medical_kb_mcp.server", "stdio"],
      "cwd": "ABSOLUTE/PATH/TO/backend",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/medical_agent",
        "LLM_API_KEY": "your-dashscope-key"
      }
    }
  }
}
```

- [ ] **Step 3: Write the MCP server README**

`backend/medical_kb_mcp/README.md` — document: purpose, the 3 tools (name, args, returns), how to run (`python -m medical_kb_mcp.server http|stdio`), env vars, and the Claude Desktop demo steps (copy `claude_desktop_config.example.json` into Claude Desktop's config, restart, ask "用发热咳嗽查可能的疾病"). Keep it under ~60 lines.

- [ ] **Step 4: Final full test run**

Run: `cd backend && pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/medical_kb_mcp/README.md claude_desktop_config.example.json
git commit -m "docs(mcp): Claude Desktop demo config + server README; M1 complete"
```

---

## Out of scope (deferred)

- **M2:** convert `analyze`/`diagnose`/`advise` nodes into LLM tool-calling agents that select MCP tools dynamically; Supervisor orchestration; triage/emergency fast-path; structured output for the analyze node.
- **M3:** eval harness + quality metrics (diagnosis hit-rate, avg follow-up turns, emergency recall).
- Disease-table admin/CRUD UI; pushing Dice scoring into SQL.
