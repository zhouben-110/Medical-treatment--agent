# Changelog

## 2026-05-31 - 数据库架构迁移

### 变更概述

将项目从 SQLite + ChromaDB 迁移至 PostgreSQL 统一数据层。

### 具体变更

**1. 应用数据库：SQLite → PostgreSQL**
- `aiosqlite` 替换为 `asyncpg`
- 数据库 URL 从 `sqlite+aiosqlite:///./medical_agent.db` 改为 `postgresql+asyncpg://...`
- 引入 Alembic 管理数据库迁移

**2. LangGraph Checkpoint：SQLite → PostgreSQL**
- `langgraph-checkpoint-sqlite` 替换为 `langgraph-checkpoint-postgres`
- 对话状态持久化从 `medical_agent_checkpoints.db` 迁移到 PostgreSQL
- 启动时自动创建 checkpoint 表（`saver.setup()`）

**3. 向量存储：ChromaDB → pgvector**
- `chromadb` + `langchain-chroma` 替换为 `langchain-postgres` + `pgvector`
- 向量数据从本地文件 `./chroma_db` 迁移到 PostgreSQL
- embedding 维度：1024（DashScope text-embedding-v3）
- 保留分批处理逻辑（DashScope API 限制 batch_size <= 10）

**4. 前端方向确认**
- 保持 Next.js 14 + React 18（与原始技术栈声明不一致，已更新文档）

### 涉及文件

| 文件 | 变更 |
|---|---|
| `backend/requirements.txt` | 依赖更新 |
| `backend/app/config.py` | 数据库 URL、移除 chroma_persist_dir |
| `backend/app/main.py` | checkpoint 从 SQLite 改为 PostgreSQL |
| `backend/app/rag/vector_store.py` | 重写为 pgvector |
| `backend/.env` | 数据库连接字符串 |
| `backend/.env.example` | 数据库连接字符串 |
| `backend/alembic/` | 新增 Alembic 迁移配置 |
| `README.md` | 更新技术栈文档 |
