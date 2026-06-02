from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app import graph as graph_module
from app.routers import chat, history, symptoms
from app.database import init_db
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()

    # 初始化 RAG 向量库
    from app.rag.vector_store import init_vector_store
    from app.rag.retriever import MedicalRetriever
    from app.nodes import disease_matcher, advisor

    try:
        vector_store = await init_vector_store(settings)
        retriever = MedicalRetriever(vector_store.as_retriever(search_kwargs={"k": 3}))
        disease_matcher.retriever = retriever
        advisor.retriever = retriever
        print("RAG vector store initialized successfully")
    except Exception as e:
        print(f"Warning: RAG initialization failed, running without RAG: {e}")

    async with AsyncExitStack() as stack:
        conn_str = settings.database_url.replace("+asyncpg", "")
        saver = await stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(conn_str)
        )
        await saver.setup()
        graph_module.medical_graph = graph_module.build_graph().compile(checkpointer=saver)
        yield


app = FastAPI(title="Medical Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
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
