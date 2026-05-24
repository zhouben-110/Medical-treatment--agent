# 医疗Agent实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建一个基于LangGraph的医疗Agent，用户描述症状后通过多轮对话获取治疗建议

**Architecture:** FastAPI后端 + LangGraph状态机处理对话流程 + Next.js前端聊天界面 + SQLite存储历史记录

**Tech Stack:** Python 3.11+, FastAPI, LangChain, LangGraph, SQLite, Next.js, TypeScript, Tailwind CSS

---

## 文件结构

```
medical-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI应用入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # SQLite数据库连接
│   │   ├── models.py            # Pydantic模型
│   │   ├── schemas.py           # 数据库表结构
│   │   ├── graph.py             # LangGraph状态机定义
│   │   ├── state.py             # 状态定义
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── symptom_analyzer.py  # 症状分析节点
│   │   │   ├── questioner.py        # 追问决策节点
│   │   │   ├── disease_matcher.py   # 疾病匹配节点
│   │   │   └── advisor.py           # 建议输出节点
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── chat.py          # 聊天接口
│   │       ├── history.py       # 历史记录接口
│   │       └── symptoms.py      # 症状分类接口
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_nodes.py
│   │   ├── test_graph.py
│   │   └── test_api.py
│   ├── requirements.txt
│   └── seed_data.py             # 症状分类初始数据
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx    # 聊天窗口
│   │   │   ├── MessageBubble.tsx # 消息气泡
│   │   │   ├── Sidebar.tsx       # 侧边栏
│   │   │   └── SymptomTags.tsx   # 症状标签
│   │   ├── api/
│   │   │   └── client.ts         # API客户端
│   │   └── types/
│   │       └── index.ts          # 类型定义
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── next.config.js
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-24-medical-agent-design.md
```

---

## Task 1: 后端项目初始化

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: 创建requirements.txt**

```txt
fastapi==0.109.0
uvicorn==0.27.0
langchain==0.1.4
langgraph==0.0.20
openai==1.12.0
pydantic==2.5.3
sqlalchemy==2.0.25
aiosqlite==0.19.0
python-dotenv==1.0.0
pytest==7.4.4
httpx==0.26.0
```

- [ ] **Step 2: 创建配置文件**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Medical Agent"
    database_url: str = "sqlite+aiosqlite:///./medical_agent.db"
    openai_api_key: str = ""
    openai_model: str = "gpt-4"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
```

- [ ] **Step 3: 创建FastAPI入口**

```python
# backend/app/main.py
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
```

- [ ] **Step 4: 安装依赖并验证**

Run: `cd backend && pip install -r requirements.txt`
Expected: 成功安装所有依赖

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat: initialize backend project with FastAPI"
```

---

## Task 2: 数据库层

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/schemas.py`
- Create: `backend/seed_data.py`

- [ ] **Step 1: 创建数据库连接**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 2: 创建数据表模型**

```python
# backend/app/schemas.py
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


def generate_id():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_id)
    created_at = Column(DateTime, server_default=func.now())
    sessions = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    diagnosis = Column(Text, nullable=True)
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", order_by="Message.timestamp")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_id)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    timestamp = Column(DateTime, server_default=func.now())
    session = relationship("Session", back_populates="messages")


class SymptomCategory(Base):
    __tablename__ = "symptom_categories"

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, unique=True)
    symptoms = relationship("Symptom", back_populates="category")


class Symptom(Base):
    __tablename__ = "symptoms"

    id = Column(String, primary_key=True, default=generate_id)
    category_id = Column(String, ForeignKey("symptom_categories.id"))
    name = Column(String)
    category = relationship("SymptomCategory", back_populates="symptoms")
```

- [ ] **Step 3: 创建初始数据脚本**

```python
# backend/seed_data.py
"""症状分类初始数据"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.schemas import SymptomCategory, Symptom

SYMPTOM_DATA = {
    "头部": ["头痛", "头晕", "耳鸣", "视力模糊", "鼻塞", "流涕"],
    "胸部": ["胸闷", "咳嗽", "气短", "心悸", "呼吸困难"],
    "腹部": ["腹痛", "腹泻", "便秘", "恶心", "呕吐", "胃胀"],
    "四肢": ["关节痛", "肌肉酸痛", "手脚麻木", "肿胀"],
    "全身": ["发热", "乏力", "失眠", "食欲不振", "体重变化"],
    "皮肤": ["皮疹", "瘙痒", "红肿", "脱皮"],
}


async def seed_symptoms():
    async with async_session() as session:
        for category_name, symptoms in SYMPTOM_DATA.items():
            category = SymptomCategory(name=category_name)
            session.add(category)
            await session.flush()
            for symptom_name in symptoms:
                symptom = Symptom(category_id=category.id, name=symptom_name)
                session.add(symptom)
        await session.commit()


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_symptoms())
```

- [ ] **Step 4: 验证数据库初始化**

Run: `cd backend && python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"`
Expected: 数据库文件medical_agent.db创建成功

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/app/schemas.py backend/seed_data.py
git commit -m "feat: add database layer with SQLAlchemy models"
```

---

## Task 3: LangGraph状态定义

**Files:**
- Create: `backend/app/state.py`
- Create: `backend/app/models.py`

- [ ] **Step 1: 创建Pydantic请求/响应模型**

```python
# backend/app/models.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    stage: str
    symptoms: List[str]
    session_id: str


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: datetime


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    message_count: int


class SessionDetailResponse(BaseModel):
    messages: List[MessageResponse]
    diagnosis: Optional[str]


class SymptomCategoryResponse(BaseModel):
    name: str
    symptoms: List[str]


class SymptomListResponse(BaseModel):
    categories: List[SymptomCategoryResponse]
```

- [ ] **Step 2: 创建LangGraph状态定义**

```python
# backend/app/state.py
from typing import List, TypedDict, Annotated
from langgraph.graph import add_messages
from datetime import datetime


class Message(TypedDict):
    role: str
    content: str
    timestamp: str


class MedicalAgentState(TypedDict):
    messages: Annotated[List[Message], add_messages]
    symptoms: List[str]
    current_stage: str
    confidence: float
    possible_diseases: List[str]
    treatment_plan: str
    need_more_info: bool
    session_id: str
    user_message: str
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/state.py backend/app/models.py
git commit -m "feat: add state and model definitions"
```

---

## Task 4: LangGraph节点实现

**Files:**
- Create: `backend/app/nodes/__init__.py`
- Create: `backend/app/nodes/symptom_analyzer.py`
- Create: `backend/app/nodes/questioner.py`
- Create: `backend/app/nodes/disease_matcher.py`
- Create: `backend/app/nodes/advisor.py`

- [ ] **Step 1: 创建症状分析节点**

```python
# backend/app/nodes/symptom_analyzer.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.config import get_settings

settings = get_settings()
llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0)

SYMPTOM_ANALYSIS_PROMPT = """你是一个医疗AI助手。请从用户的描述中提取症状信息。

用户描述: {user_message}

已识别的症状: {existing_symptoms}

请返回:
1. 新识别的症状列表（用逗号分隔）
2. 症状的严重程度（轻度/中度/重度）
3. 是否需要更多信息才能初步判断

返回格式（严格遵守）:
symptoms: 症状1, 症状2, ...
severity: 轻度/中度/重度
need_more_info: true/false"""


async def analyze_symptoms(state: MedicalAgentState) -> dict:
    """从用户消息中提取症状"""
    prompt = ChatPromptTemplate.from_template(SYMPTOM_ANALYSIS_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "user_message": state["user_message"],
        "existing_symptoms": ", ".join(state.get("symptoms", []))
    })

    content = response.content
    # 解析响应
    symptoms_line = [line for line in content.split("\n") if line.startswith("symptoms:")][0]
    new_symptoms = [s.strip() for s in symptoms_line.replace("symptoms:", "").split(",") if s.strip()]

    need_more_line = [line for line in content.split("\n") if line.startswith("need_more_info:")][0]
    need_more = "true" in need_more_line.lower()

    # 合并症状
    all_symptoms = list(set(state.get("symptoms", []) + new_symptoms))

    return {
        "symptoms": all_symptoms,
        "need_more_info": need_more,
        "current_stage": "analyzing"
    }
```

- [ ] **Step 2: 创建追问决策节点**

```python
# backend/app/nodes/questioner.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.config import get_settings

settings = get_settings()
llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0.3)

QUESTION_PROMPT = """你是一个医疗AI助手。根据已知症状，生成追问问题。

已知症状: {symptoms}
对话历史: {conversation_history}

请生成1-3个关键追问，帮助判断病情。重点关注:
1. 症状持续时间
2. 伴随症状
3. 既往病史
4. 过敏史

直接返回追问内容，不要有多余格式。"""


async def generate_question(state: MedicalAgentState) -> dict:
    """生成追问问题"""
    prompt = ChatPromptTemplate.from_template(QUESTION_PROMPT)
    chain = prompt | llm

    history = "\n".join([f"{m['role']}: {m['content']}" for m in state.get("messages", [])[-5:]])

    response = await chain.ainvoke({
        "symptoms": ", ".join(state.get("symptoms", [])),
        "conversation_history": history
    })

    return {
        "messages": [{"role": "assistant", "content": response.content}],
        "current_stage": "questioning"
    }
```

- [ ] **Step 3: 创建疾病匹配节点**

```python
# backend/app/nodes/disease_matcher.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.config import get_settings

settings = get_settings()
llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0)

DISEASE_MATCH_PROMPT = """你是一个医疗AI助手。根据症状组合，匹配可能的疾病。

症状列表: {symptoms}
对话历史: {conversation_history}

请返回:
1. 可能的疾病列表（最多3个，按可能性排序）
2. 每个疾病的置信度（0-100）
3. 简要说明判断依据

返回格式（严格遵守）:
disease1: 疾病名 (置信度%)
disease2: 疾病名 (置信度%)
disease3: 疾病名 (置信度%)
reason: 判断依据"""


async def match_diseases(state: MedicalAgentState) -> dict:
    """匹配可能的疾病"""
    prompt = ChatPromptTemplate.from_template(DISEASE_MATCH_PROMPT)
    chain = prompt | llm

    history = "\n".join([f"{m['role']}: {m['content']}" for m in state.get("messages", [])[-5:]])

    response = await chain.ainvoke({
        "symptoms": ", ".join(state.get("symptoms", [])),
        "conversation_history": history
    })

    content = response.content
    diseases = []
    confidence = 0.0

    for line in content.split("\n"):
        if line.startswith("disease"):
            parts = line.split(":")[1].strip()
            disease_name = parts.split("(")[0].strip()
            conf_str = parts.split("(")[1].replace("%)", "").strip() if "(" in parts else "50"
            diseases.append(disease_name)
            if not confidence:
                confidence = float(conf_str) / 100

    return {
        "possible_diseases": diseases,
        "confidence": confidence,
        "current_stage": "diagnosing"
    }
```

- [ ] **Step 4: 创建建议输出节点**

```python
# backend/app/nodes/advisor.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.state import MedicalAgentState
from app.config import get_settings

settings = get_settings()
llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0.3)

ADVICE_PROMPT = """你是一个医疗AI助手。根据诊断结果，生成治疗建议。

可能的疾病: {diseases}
症状: {symptoms}
置信度: {confidence}

请生成:
1. 治疗建议（包括用药建议、生活调理）
2. 注意事项
3. 是否需要就医

重要：在回复末尾必须加上免责声明："以上内容仅供参考，不构成医疗建议。如有不适，请及时就医。"

返回完整的建议内容。"""


async def generate_advice(state: MedicalAgentState) -> dict:
    """生成治疗建议"""
    prompt = ChatPromptTemplate.from_template(ADVICE_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "diseases": ", ".join(state.get("possible_diseases", [])),
        "symptoms": ", ".join(state.get("symptoms", [])),
        "confidence": f"{state.get('confidence', 0) * 100:.0f}%"
    })

    return {
        "messages": [{"role": "assistant", "content": response.content}],
        "treatment_plan": response.content,
        "current_stage": "completed"
    }
```

- [ ] **Step 5: 创建nodes __init__.py**

```python
# backend/app/nodes/__init__.py
from .symptom_analyzer import analyze_symptoms
from .questioner import generate_question
from .disease_matcher import match_diseases
from .advisor import generate_advice

__all__ = ["analyze_symptoms", "generate_question", "match_diseases", "generate_advice"]
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/nodes/
git commit -m "feat: implement LangGraph nodes for medical diagnosis flow"
```

---

## Task 5: LangGraph状态机

**Files:**
- Create: `backend/app/graph.py`

- [ ] **Step 1: 创建状态机图**

```python
# backend/app/graph.py
from langgraph.graph import StateGraph, END
from app.state import MedicalAgentState
from app.nodes import analyze_symptoms, generate_question, match_diseases, generate_advice


def should_continue(state: MedicalAgentState) -> str:
    """判断是否需要继续追问"""
    if state.get("need_more_info", True) and len(state.get("messages", [])) < 10:
        return "question"
    return "diagnose"


def create_medical_graph():
    """创建医疗诊断状态机"""
    workflow = StateGraph(MedicalAgentState)

    # 添加节点
    workflow.add_node("analyze", analyze_symptoms)
    workflow.add_node("question", generate_question)
    workflow.add_node("diagnose", match_diseases)
    workflow.add_node("advise", generate_advice)

    # 设置入口
    workflow.set_entry_point("analyze")

    # 添加边
    workflow.add_conditional_edges(
        "analyze",
        should_continue,
        {
            "question": "question",
            "diagnose": "diagnose"
        }
    )
    workflow.add_edge("question", "analyze")
    workflow.add_edge("diagnose", "advise")
    workflow.add_edge("advise", END)

    return workflow.compile()


# 全局图实例
medical_graph = create_medical_graph()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/graph.py
git commit -m "feat: implement LangGraph state machine for diagnosis flow"
```

---

## Task 6: API路由实现

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/chat.py`
- Create: `backend/app/routers/history.py`
- Create: `backend/app/routers/symptoms.py`

- [ ] **Step 1: 创建聊天路由**

```python
# backend/app/routers/chat.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ChatRequest, ChatResponse
from app.schemas import Session, Message
from app.graph import medical_graph
from app.state import Message as StateMessage
from datetime import datetime
import uuid

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    # 获取或创建会话
    if request.session_id:
        session = await db.get(Session, request.session_id)
        if not session:
            session = Session(id=request.session_id, title=request.message[:20])
            db.add(session)
    else:
        session = Session(title=request.message[:20])
        db.add(session)
        await db.flush()

    # 保存用户消息
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=request.message
    )
    db.add(user_msg)

    # 获取历史消息
    from sqlalchemy import select
    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.timestamp)
    )
    history = result.scalars().all()

    messages = [{"role": m.role, "content": m.content} for m in history]

    # 调用状态机
    initial_state = {
        "messages": messages,
        "symptoms": [],
        "current_stage": "start",
        "confidence": 0.0,
        "possible_diseases": [],
        "treatment_plan": "",
        "need_more_info": True,
        "session_id": session.id,
        "user_message": request.message
    }

    result = await medical_graph.ainvoke(initial_state)

    # 获取AI回复
    ai_reply = result["messages"][-1]["content"] if result["messages"] else "抱歉，我无法处理您的请求。"

    # 保存AI回复
    ai_msg = Message(
        session_id=session.id,
        role="assistant",
        content=ai_reply
    )
    db.add(ai_msg)

    # 更新会话诊断
    if result.get("treatment_plan"):
        session.diagnosis = result["possible_diseases"][0] if result["possible_diseases"] else None

    await db.commit()

    return ChatResponse(
        reply=ai_reply,
        stage=result.get("current_stage", "unknown"),
        symptoms=result.get("symptoms", []),
        session_id=session.id
    )
```

- [ ] **Step 2: 创建历史记录路由**

```python
# backend/app/routers/history.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import SessionResponse, SessionDetailResponse, MessageResponse
from app.schemas import Session, Message

router = APIRouter()


@router.get("/history", response_model=list[SessionResponse])
async def get_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()

    response = []
    for session in sessions:
        msg_count = await db.execute(
            select(func.count()).where(Message.session_id == session.id)
        )
        count = msg_count.scalar()
        response.append(SessionResponse(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            message_count=count
        ))

    return response


@router.get("/history/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        return {"error": "Session not found"}, 404

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.timestamp)
    )
    messages = result.scalars().all()

    return SessionDetailResponse(
        messages=[MessageResponse(
            role=m.role,
            content=m.content,
            timestamp=m.timestamp
        ) for m in messages],
        diagnosis=session.diagnosis
    )
```

- [ ] **Step 3: 创建症状分类路由**

```python
# backend/app/routers/symptoms.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import SymptomListResponse, SymptomCategoryResponse
from app.schemas import SymptomCategory, Symptom

router = APIRouter()


@router.get("/symptoms", response_model=SymptomListResponse)
async def get_symptoms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SymptomCategory))
    categories = result.scalars().all()

    response = []
    for category in categories:
        symptoms_result = await db.execute(
            select(Symptom).where(Symptom.category_id == category.id)
        )
        symptoms = symptoms_result.scalars().all()
        response.append(SymptomCategoryResponse(
            name=category.name,
            symptoms=[s.name for s in symptoms]
        ))

    return SymptomListResponse(categories=response)
```

- [ ] **Step 4: 创建路由 __init__.py**

```python
# backend/app/routers/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/
git commit -m "feat: implement API routes for chat, history, and symptoms"
```

---

## Task 7: 后端测试

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: 创建API测试**

```python
# backend/tests/test_api.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Medical Agent API"}


@pytest.mark.asyncio
async def test_get_symptoms(client):
    response = await client.get("/api/symptoms")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data


@pytest.mark.asyncio
async def test_chat(client):
    response = await client.post("/api/chat", json={
        "message": "我最近总是头痛"
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "session_id" in data


@pytest.mark.asyncio
async def test_get_history(client):
    response = await client.get("/api/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add backend/tests/
git commit -m "test: add API endpoint tests"
```

---

## Task 8: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css`

- [ ] **Step 1: 创建package.json**

```json
{
  "name": "medical-agent-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.1.0",
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "tailwindcss": "^3.3.0",
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: 创建Next.js配置**

```javascript
// frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
```

- [ ] **Step 3: 创建Tailwind配置**

```typescript
// frontend/tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 4: 创建布局文件**

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '医疗健康助手',
  description: 'AI驱动的症状分析与治疗建议',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 5: 创建全局样式**

```css
/* frontend/src/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --foreground-rgb: 0, 0, 0;
  --background-start-rgb: 214, 219, 220;
  --background-end-rgb: 255, 255, 255;
}

body {
  color: rgb(var(--foreground-rgb));
  background: linear-gradient(
      to bottom,
      transparent,
      rgb(var(--background-end-rgb))
    )
    rgb(var(--background-start-rgb));
}
```

- [ ] **Step 6: 创建主页面**

```tsx
// frontend/src/app/page.tsx
export default function Home() {
  return (
    <main className="flex min-h-screen">
      <div className="w-64 bg-gray-100 p-4">
        <h2 className="text-lg font-bold mb-4">历史记录</h2>
      </div>
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-4">
          <h1 className="text-2xl font-bold">医疗健康助手</h1>
          <p className="text-gray-600 mt-2">描述您的症状，AI将为您提供初步建议</p>
        </div>
        <div className="p-4 border-t">
          <div className="flex gap-2">
            <input
              className="flex-1 p-2 border rounded"
              placeholder="描述您的症状..."
            />
            <button className="px-4 py-2 bg-blue-500 text-white rounded">
              发送
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 7: 安装依赖并验证**

Run: `cd frontend && npm install && npm run build`
Expected: 构建成功

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Next.js frontend project"
```

---

## Task 9: 前端组件实现

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/ChatWindow.tsx`
- Create: `frontend/src/components/MessageBubble.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/SymptomTags.tsx`

- [ ] **Step 1: 创建类型定义**

```typescript
// frontend/src/types/index.ts
export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}

export interface ChatResponse {
  reply: string;
  stage: string;
  symptoms: string[];
  session_id: string;
}

export interface SymptomCategory {
  name: string;
  symptoms: string[];
}
```

- [ ] **Step 2: 创建API客户端**

```typescript
// frontend/src/api/client.ts
import { ChatResponse, Session, SymptomCategory } from '@/types';

const API_BASE = '/api';

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  return response.json();
}

export async function getHistory(): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/history`);
  return response.json();
}

export async function getSessionDetail(sessionId: string) {
  const response = await fetch(`${API_BASE}/history/${sessionId}`);
  return response.json();
}

export async function getSymptoms(): Promise<{ categories: SymptomCategory[] }> {
  const response = await fetch(`${API_BASE}/symptoms`);
  return response.json();
}
```

- [ ] **Step 3: 创建消息气泡组件**

```tsx
// frontend/src/components/MessageBubble.tsx
import { Message } from '@/types';

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] p-3 rounded-lg ${
          isUser
            ? 'bg-blue-500 text-white rounded-br-none'
            : 'bg-gray-200 text-gray-800 rounded-bl-none'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 创建症状标签组件**

```tsx
// frontend/src/components/SymptomTags.tsx
interface Props {
  symptoms: string[];
}

export default function SymptomTags({ symptoms }: Props) {
  if (!symptoms.length) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {symptoms.map((symptom, index) => (
        <span
          key={index}
          className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm"
        >
          {symptom}
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: 创建侧边栏组件**

```tsx
// frontend/src/components/Sidebar.tsx
import { Session } from '@/types';

interface Props {
  sessions: Session[];
  currentSessionId?: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
}

export default function Sidebar({ sessions, currentSessionId, onSelectSession, onNewSession }: Props) {
  return (
    <div className="w-64 bg-gray-100 p-4 flex flex-col">
      <button
        onClick={onNewSession}
        className="w-full mb-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
      >
        + 新对话
      </button>
      <h3 className="text-sm font-semibold text-gray-500 mb-2">历史记录</h3>
      <div className="flex-1 overflow-y-auto">
        {sessions.map((session) => (
          <div
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            className={`p-3 mb-2 rounded cursor-pointer ${
              currentSessionId === session.id
                ? 'bg-blue-100 border-blue-300'
                : 'bg-white hover:bg-gray-50'
            }`}
          >
            <p className="text-sm font-medium truncate">{session.title}</p>
            <p className="text-xs text-gray-500">{session.message_count} 条消息</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: 创建聊天窗口组件**

```tsx
// frontend/src/components/ChatWindow.tsx
'use client';

import { useState, useRef, useEffect } from 'react';
import { Message, Session } from '@/types';
import { sendMessage, getHistory, getSessionDetail } from '@/api/client';
import MessageBubble from './MessageBubble';
import SymptomTags from './SymptomTags';
import Sidebar from './Sidebar';

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>();
  const [symptoms, setSymptoms] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadHistory = async () => {
    const data = await getHistory();
    setSessions(data);
  };

  const loadSession = async (sessionId: string) => {
    const data = await getSessionDetail(sessionId);
    setMessages(data.messages);
    setCurrentSessionId(sessionId);
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendMessage(input, currentSessionId);
      const aiMessage: Message = { role: 'assistant', content: response.reply };
      setMessages((prev) => [...prev, aiMessage]);
      setSymptoms(response.symptoms);
      setCurrentSessionId(response.session_id);
      loadHistory();
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleNewSession = () => {
    setMessages([]);
    setCurrentSessionId(undefined);
    setSymptoms([]);
  };

  return (
    <div className="flex h-screen">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={loadSession}
        onNewSession={handleNewSession}
      />
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 mt-20">
              <h2 className="text-2xl font-bold mb-2">医疗健康助手</h2>
              <p>描述您的症状，AI将为您提供初步建议</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}
          {symptoms.length > 0 && <SymptomTags symptoms={symptoms} />}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-200 p-3 rounded-lg rounded-bl-none">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="p-4 border-t">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              className="flex-1 p-2 border rounded focus:outline-none focus:border-blue-500"
              placeholder="描述您的症状..."
              disabled={loading}
            />
            <button
              onClick={handleSend}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-400"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: 更新主页面使用ChatWindow**

```tsx
// frontend/src/app/page.tsx
import ChatWindow from '@/components/ChatWindow';

export default function Home() {
  return <ChatWindow />;
}
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: implement chat UI components"
```

---

## Task 10: 集成测试

**Files:**
- Create: `backend/tests/test_integration.py`

- [ ] **Step 1: 创建集成测试**

```python
# backend/tests/test_integration.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_full_diagnosis_flow(client):
    """测试完整的诊断流程"""
    # 第一轮：发送症状
    response1 = await client.post("/api/chat", json={
        "message": "我最近三天一直头痛，还有点发烧"
    })
    assert response1.status_code == 200
    data1 = response1.json()
    session_id = data1["session_id"]
    assert session_id is not None

    # 第二轮：回答追问
    response2 = await client.post("/api/chat", json={
        "message": "体温大概38度，没有其他症状",
        "session_id": session_id
    })
    assert response2.status_code == 200
    data2 = response2.json()
    assert "reply" in data2

    # 验证历史记录
    history = await client.get(f"/api/history/{session_id}")
    assert history.status_code == 200
    history_data = history.json()
    assert len(history_data["messages"]) >= 4  # 至少2轮对话
```

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && pytest tests/test_integration.py -v`
Expected: 测试通过

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_integration.py
git commit -m "test: add integration test for full diagnosis flow"
```

---

## Task 11: 启动脚本和文档

**Files:**
- Create: `backend/.env.example`
- Create: `README.md`

- [ ] **Step 1: 创建环境变量示例**

```bash
# backend/.env.example
OPENAI_API_KEY=your-openai-api-key-here
DATABASE_URL=sqlite+aiosqlite:///./medical_agent.db
```

- [ ] **Step 2: 创建README**

```markdown
# 医疗健康助手

AI驱动的症状分析与治疗建议系统

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入你的 OpenAI API Key
python seed_data.py  # 初始化症状数据
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 技术栈

- **后端**: FastAPI + LangChain + LangGraph
- **前端**: Next.js + TypeScript + Tailwind CSS
- **数据库**: SQLite

## 架构

用户描述症状 → 症状分析 → 追问决策 → 疾病匹配 → 治疗建议
```

- [ ] **Step 3: Commit**

```bash
git add backend/.env.example README.md
git commit -m "docs: add README and environment example"
```

---

## 自审检查清单

- [ ] 所有API端点已实现
- [ ] LangGraph状态机完整（4个节点）
- [ ] 数据库模型与设计文档一致
- [ ] 前端组件覆盖所有功能
- [ ] 测试覆盖单元测试和集成测试
- [ ] 无TBD/TODO占位符
- [ ] 所有文件路径准确
- [ ] 代码示例完整可执行