# 医疗健康助手

AI 驱动的症状分析与治疗建议系统，基于 LangGraph 状态机实现多轮问诊。

## 技术栈

### 后端

| 技术 | 用途 |
|---|---|
| FastAPI | Web 框架 |
| SQLAlchemy 2.x + asyncpg | 异步 ORM |
| PostgreSQL 17 | 主数据库 |
| pgvector 0.8.0 | 向量检索 |
| Alembic | 数据库迁移 |
| LangGraph | AI 对话状态机 |
| LangGraph Checkpoint Postgres | 对话状态持久化 |
| Uvicorn | ASGI 服务器 |

### AI / RAG

| 技术 | 用途 |
|---|---|
| DashScope API (qwen-plus) | LLM（OpenAI 兼容接口） |
| DashScope text-embedding-v3 | 文本向量化（1024 维） |
| LangChain | RAG 流程编排 |
| langchain-postgres (PGVector) | 向量存储与检索 |

### 前端

| 技术 | 用途 |
|---|---|
| Next.js 14 (App Router) | React 框架 |
| React 18 + TypeScript | UI |
| Tailwind CSS 3.3 | 样式 |
| 原生 fetch + SSE | HTTP 与流式通信 |

## 快速开始

### 1. PostgreSQL + pgvector

确保 PostgreSQL 运行在 `localhost:5432`，然后：

```sql
CREATE DATABASE medical_agent;
\c medical_agent
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 编辑 .env 填入 DashScope API Key
alembic upgrade head   # 创建数据库表
uvicorn app.main:app --reload --port 8000
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 项目结构

```
backend/
├── app/
│   ├── config.py           # Pydantic Settings 配置
│   ├── database.py         # SQLAlchemy 异步引擎
│   ├── schemas.py          # ORM 模型（5 张业务表）
│   ├── models.py           # Pydantic 请求/响应模型
│   ├── state.py            # LangGraph 状态定义
│   ├── graph.py            # 状态机（4 节点）
│   ├── main.py             # FastAPI 入口 + lifespan
│   ├── nodes/              # 状态机节点
│   │   ├── symptom_analyzer.py
│   │   ├── questioner.py
│   │   ├── disease_matcher.py
│   │   └── advisor.py
│   ├── rag/                # RAG 检索
│   │   ├── embeddings.py       # DashScope 嵌入
│   │   ├── vector_store.py     # pgvector 初始化
│   │   ├── retriever.py        # 混合检索器
│   │   └── knowledge_base.py   # 结构化疾病库
│   └── routers/            # API 路由
│       ├── chat.py         # 对话（含 SSE 流式）
│       ├── history.py      # 历史记录
│       └── symptoms.py     # 症状列表
├── alembic/                # 数据库迁移
├── data/guidelines/        # 医学指南（9 篇 .md）
└── requirements.txt

frontend/
├── src/
│   ├── app/                # Next.js 页面
│   ├── api/client.ts       # API 客户端
│   ├── types/index.ts      # TypeScript 类型
│   └── components/         # UI 组件
└── next.config.js          # API 代理
```

## 数据库

| 表 | 说明 |
|---|---|
| `users` | 用户 |
| `sessions` | 问诊会话 |
| `messages` | 对话消息 |
| `symptom_categories` | 症状分类 |
| `symptoms` | 症状 |
| `langchain_pg_*` | pgvector 向量数据 |
| `checkpoints*` | LangGraph 状态 |

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | 发送消息 |
| POST | `/api/chat/stream` | SSE 流式对话 |
| GET | `/api/history` | 会话列表 |
| GET | `/api/history/{id}` | 会话详情 |
| DELETE | `/api/history/{id}` | 删除会话 |
| GET | `/api/symptoms` | 症状分类 |

## 对话流程

```
用户输入 → [症状分析] → 需要更多信息？
                          ├─ 是 → [追问] → END（等待回复）
                          └─ 否 → [疾病匹配] → [治疗建议] → END
```

最多追问 5 轮，结合 RAG 检索医学指南文档给出诊断和建议。
