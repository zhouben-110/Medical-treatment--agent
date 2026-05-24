from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, history, symptoms
from app.database import init_db

app = FastAPI(title="Medical Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(symptoms.router, prefix="/api")


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/")
async def root():
    return {"message": "Medical Agent API"}
