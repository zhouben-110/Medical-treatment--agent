import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app import graph as graph_module
from app.routers import chat, history, symptoms
from app.database import init_db
from app.config import get_settings
from app.redis import init_redis, close_redis, check_rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    await init_redis(settings.redis_url)

    from app.mcp_client import load_tools
    from app.rag.retriever import MedicalRetriever
    import app.nodes.diagnose_and_advise as _da_mod

    try:
        tools = await load_tools()
        retriever = MedicalRetriever(tools)
        _da_mod.retriever = retriever
    except Exception as e:
        print(f"Warning: MCP retriever init failed, running without RAG: {e}")

    async with AsyncExitStack() as stack:
        stack.push_async_callback(close_redis)
        conn_str = settings.database_url.replace("+asyncpg", "")
        saver = await stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(conn_str)
        )
        await saver.setup()
        graph_module.medical_graph = graph_module.build_graph().compile(checkpointer=saver)
        yield


app = FastAPI(title="Medical Agent API", lifespan=lifespan)

settings = get_settings()


@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    allowed = await check_rate_limit("rl:global", limit=60, window=60)
    if not allowed:
        return JSONResponse(status_code=429, content={"detail": "Global rate limit exceeded"})
    return await call_next(request)

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

    # Redis 状态
    from app.redis import get_redis as _get_redis, get_active_session_count
    r = _get_redis()
    checks["redis"] = "ok" if r else "unavailable"
    active = await get_active_session_count()
    if active >= 0:
        checks["active_sessions"] = active

    return checks
