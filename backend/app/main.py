import sys
import os
import asyncio

# 将 backend 根目录注入 sys.path 和环境变量 PYTHONPATH，确保 stdio 子进程可以顺利导入 medical_kb_mcp 模块
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
os.environ["PYTHONPATH"] = backend_dir + (os.path.pathsep + os.environ.get("PYTHONPATH", "") if os.environ.get("PYTHONPATH") else "")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app import graph as graph_module
from app.routers import chat, history, symptoms, auth, admin
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
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(symptoms.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Medical Agent API"}


@app.get("/health")
async def health():
    """简化版健康检查，不暴露内部状态"""
    return {"status": "ok"}
