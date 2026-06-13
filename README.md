# 医疗健康助手

AI 驱动的多 Agent 症状分析与治疗建议系统。基于 LangGraph Supervisor 模式实现多 Agent 协作，MCP 协议解耦知识层，Pydantic 结构化输出保证数据质量。

## 技术栈

### 后端

| 技术 | 用途 |
|---|---|
| FastAPI | Web 框架 |
| SQLAlchemy 2.x + asyncpg | 异步 ORM |
| PostgreSQL 17 | 主数据库 |
| pgvector 0.8.0 | 向量检索 |
| Alembic | 数据库迁移 |
| LangGraph | 多 Agent 状态机 |
| LangGraph Supervisor | Supervisor 多 Agent 编排 |
| LangGraph Checkpoint Postgres | 对话状态持久化 |
| Uvicorn | ASGI 服务器 |

### AI / RAG

| 技术 | 用途 |
|---|---|
| DashScope API (qwen-plus) | LLM（OpenAI 兼容接口） |
| DashScope text-embedding-v3 | 文本向量化（1024 维） |
| LangChain | RAG 流程编排 |
| langchain-postgres (PGVector) | 向量存储与检索 |
| MCP (Model Context Protocol) | 知识层封装（Claude Desktop 通过 stdio 消费） |
| Pydantic 结构化输出 | 症状提取 + 分诊输出 |

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
python -m medical_kb_mcp.seed_diseases   # 灌入 25 种疾病数据（幂等）
```

> **关于指南向量库**：`search_guidelines` 读取**已存在**的 `medical_guidelines` 向量集合。全新空库下该集合为空，指南检索会**优雅降级为空结果**（结构化疾病检索不受影响）。重新 ingest `data/guidelines/*.md` 是 M1 之后的跟进项，详见 [`backend/medical_kb_mcp/README.md`](backend/medical_kb_mcp/README.md)。

启动 FastAPI 应用：
```bash
uvicorn app.main:app --reload --port 8000
# Windows 已在 app/main.py 顶部设置 SelectorEventLoop，直接 uvicorn 即可
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

### 4. Claude Desktop 集成

MCP Server 同时支持 stdio 模式，可直接挂载到 Claude Desktop：

```json
{
  "mcpServers": {
    "medical-kb": {
      "command": "python",
      "args": ["-m", "medical_kb_mcp.server"],
      "cwd": "你的路径/backend"
    }
  }
}
```

## 环境变量

后端配置全部走 `backend/.env`（复制自 `.env.example`）：

| 变量 | 用途 | 默认 / 示例 |
|---|---|---|
| `LLM_API_KEY` | DashScope API Key（LLM 与嵌入共用） | 必填 |
| `LLM_MODEL` | 对话模型 | `qwen-plus` |
| `LLM_BASE_URL` | LLM OpenAI 兼容端点 | DashScope compatible-mode |
| `DATABASE_URL` | Postgres 连接串（asyncpg 驱动） | `postgresql+asyncpg://...:5432/medical_agent` |
| `EMBEDDING_MODEL` | 嵌入模型（1024 维） | `text-embedding-v3` |
| `EMBEDDING_BASE_URL` | 嵌入端点 | DashScope compatible-mode |
| `DATA_DIR` | 指南 `.md` 数据目录 | `./data` |
| `API_KEY` | API 鉴权密钥；**留空则关闭鉴权（开发模式）** | — |
| `CORS_ORIGINS` | 允许的前端来源（逗号分隔） | `http://localhost:3000,...` |
| `SQL_ECHO` | 是否打印 SQL | `false` |
| `LANGCHAIN_TRACING_V2` | 开启 LangSmith 追踪 | `false` |
| `LANGCHAIN_API_KEY` | LangSmith Key | — |
| `LANGCHAIN_PROJECT` | LangSmith 项目名 | `medical-agent` |
| `MCP_HOST` / `MCP_PORT` | MCP server 监听地址（Claude Desktop 用） | `127.0.0.1` / `8765` |

## 项目结构

```
backend/
├── app/
│   ├── config.py           # Pydantic Settings 配置
│   ├── database.py         # SQLAlchemy 异步引擎
│   ├── models.py           # ORM 模型（5 张业务表）
│   ├── schemas.py          # Pydantic 请求/响应模型
│   ├── state.py            # LangGraph 状态定义（含急诊字段）
│   ├── graph.py            # Supervisor 多 Agent 路由
│   ├── main.py             # FastAPI 入口 + lifespan + /health
│   ├── auth.py             # API Key 认证（hmac.compare_digest）
│   ├── llm.py              # LLM 实例工厂（带缓存）
│   ├── summarizer.py       # 对话摘要机制（>12 条消息触发）
│   ├── cache.py            # 诊断结果缓存（1h TTL）
│   ├── nodes/              # Agent 节点
│   │   ├── triage.py           # 分诊/急诊 Agent（确定性红旗检测 + LLM）
│   │   ├── symptom_analyzer.py # 症状提取（Pydantic 结构化输出）
│   │   ├── questioner.py       # 追问 Agent
│   │   ├── disease_matcher.py  # 疾病匹配（结构化 JSON + 缓存）
│   │   └── advisor.py          # 治疗建议 Agent
│   ├── rag/                # RAG 检索（直接调用知识层函数）
│   │   └── retriever.py        # 调 medical_kb_mcp → 拼 context
│   └── routers/            # API 路由
│       ├── chat.py         # 对话（含 SSE 流式 + 进度事件）
│       ├── history.py      # 历史记录
│       └── symptoms.py     # 症状列表
├── medical_kb_mcp/         # 独立 MCP Server（可独立部署）
│   ├── server.py           # FastMCP 应用 + 3 个原子工具
│   ├── db.py               # Postgres 疾病表访问（Dice 匹配）
│   ├── vectors.py          # pgvector + DashScope 嵌入
│   ├── models.py           # Disease ORM 模型
│   ├── config.py           # MCPSettings（读同一 .env）
│   └── seed_diseases.py    # 25 种疾病种子数据
├── evals/                  # Eval 工具
│   ├── dataset.py          # 35 个 eval case（25 正常 + 5 急诊 + 5 模糊）
│   ├── runner.py           # eval 执行引擎（mock / real 两种模式）
│   ├── metrics.py          # 指标计算（命中率/追问轮数/急症召回率）
│   └── test_eval.py        # pytest 集成
├── alembic/                # 数据库迁移
├── data/guidelines/        # 医学指南（9 篇 .md）
└── requirements.txt

frontend/
├── src/
│   ├── app/                # Next.js 页面
│   ├── api/client.ts       # API 客户端
│   ├── types/index.ts      # TypeScript 类型
│   ├── hooks/              # 自定义 Hook
│   │   ├── useChat.ts          # 聊天状态管理
│   │   └── useSession.ts       # 会话管理
│   └── components/         # UI 组件
└── next.config.js          # API 代理
```

## 多 Agent 架构（M2）

系统采用 **Supervisor 多 Agent 模式**，每个 Agent 有明确职责：

```
用户输入 → Supervisor → Triage（分诊）
                          ├─ 红旗命中 → 急救短路（END）
                          └─ 正常 → Supervisor → Analyze（症状提取）
                                      └─ Supervisor → Question（追问）/ Diagnose（诊断）
                                                        └─ Advise（建议）→ END
```

| Agent | 职责 | 技术特点 |
|---|---|---|
| **Supervisor** | 路由决策 | LLM + 确定性兜底，LangSmith 可见 |
| **Triage** | 急诊检测 | 确定性红旗关键词（29 个）+ LLM 结构化输出 |
| **Analyze** | 症状提取 | Pydantic `SymptomExtraction` 结构化输出 |
| **Question** | 追问 | 最多 5 轮 |
| **Diagnose** | 疾病匹配 | RAG 检索（直接调用知识层）+ LLM 推理 |
| **Advise** | 治疗建议 | 知识库 + 医学指南 |

## MCP Server（M1）

`medical_kb_mcp` 包提供 3 个原子工具，App 侧直接函数调用，Claude Desktop 通过 stdio 消费：

| 工具 | 用途 |
|---|---|
| `search_diseases_by_symptoms` | 症状→疾病匹配（Postgres ARRAY + GIN + Dice） |
| `get_disease_detail` | 疾病详情查询 |
| `search_guidelines` | 医学指南语义检索（pgvector + DashScope） |

App 侧直接调用 `medical_kb_mcp.db` / `vectors` 模块的函数，无需启动独立进程。Claude Desktop 通过 stdio 模式挂载（见下方集成配置）。

## Eval 工具（M3）

```bash
cd backend
python -m pytest evals/test_eval.py -v -s
```

三个核心指标：

| 指标 | 计算方式 | 当前值 |
|---|---|---|
| 诊断命中率 | expected_disease ∈ Top-3 results | 92.0% |
| 平均追问轮数 | start→diagnose 间的 question 节点数 | 0.7 |
| 急症召回率 | emergency case 中被正确检出的比例 | 100.0% |

支持 mock（快速 CI）和 real（完整 E2E）两种模式。

## 数据库

| 表 | 说明 |
|---|---|
| `users` | 用户 |
| `sessions` | 问诊会话 |
| `messages` | 对话消息 |
| `symptom_categories` | 症状分类 |
| `symptoms` | 症状 |
| `diseases` | 疾病知识库（25 种，MCP Server 管理） |
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
| GET | `/health` | 健康检查（数据库/连接池/LangGraph/缓存） |

### 鉴权

除 `/health` 外，所有 `/api/*` 路由都通过路由级依赖 `verify_api_key` 校验请求头 `X-API-Key`（值取 `.env` 的 `API_KEY`）。若 `.env` 未设置 `API_KEY`，则**跳过校验（开发模式）**。

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/symptoms
```

## 测试

```bash
cd backend

# 全量测试（不含需要数据库的 API/集成测试）
python -m pytest tests/ -v --ignore=tests/test_api.py --ignore=tests/test_integration.py

# Eval 测试
python -m pytest evals/test_eval.py -v -s

# 单独模块测试
python -m pytest tests/test_triage.py -v
python -m pytest tests/test_symptom_analyzer_structured.py -v
```
