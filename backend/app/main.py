from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app import graph as graph_module
from app.routers import chat, history, symptoms
from app.database import init_db
from app.config import get_settings

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


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


app = FastAPI(title="Medical Agent API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(symptoms.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Medical Agent API"}


@app.get("/health")
async def health():
    from sqlalchemy import text
    from app.database import async_session, engine

    checks = {"status": "ok"}

    # 数据库连接检查
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

    # 连接池状态
    pool = engine.pool
    checks["pool"] = {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }

    # LangGraph 状态检查
    try:
        if graph_module.medical_graph is not None:
            checks["langgraph"] = "ok"
        else:
            checks["langgraph"] = "not initialized"
            checks["status"] = "degraded"
    except Exception as e:
        checks["langgraph"] = f"error: {e}"
        checks["status"] = "degraded"

    # 缓存状态
    try:
        from app.cache import _cache
        checks["cache"] = {"diagnosis_entries": len(_cache)}
    except Exception:
        pass

    return checks
