# Medical-KB MCP Server 设计文档(M1)

- **日期**:2026-06-06
- **状态**:已评审通过,待实现
- **作者**:协作设计(brainstorming)
- **里程碑**:M1 —— 知识层抽成独立 MCP Server

---

## 1. 背景

当前医疗 agent 是一个 **LangGraph 工作流**(非自主 agent):`analyze → question 循环 / diagnose → advise`,四个节点是四次固定的 LLM 调用,路由由 `graph.py` 硬编码。

医学知识检索目前是**进程内直接函数调用**,完全没有 MCP:

- `backend/app/rag/knowledge_base.py`:25 种疾病**硬编码在 Python list**,Dice 系数做症状匹配。
- `backend/app/rag/vector_store.py` + `embeddings.py`:pgvector + DashScope 嵌入,检索 `data/guidelines/*.md` 诊疗指南。
- `backend/app/rag/retriever.py`:合并上述两通道,供 `disease_matcher`、`advisor` 节点调用。
- `backend/app/main.py` lifespan 把 retriever 作为模块全局变量注入进节点,耦合紧。

**项目定位**:学习 / 作品集展示。因此优先展示「可复用、解耦的知识服务 + 标准 MCP 接口」这一当下热门且可演示的能力。

## 2. 目标与非目标

### M1 目标

1. 把医学知识层(结构化疾病表 + 向量指南检索)抽成**独立的 Medical-KB MCP Server**(独立进程、独立部署)。
2. 疾病数据从硬编码 Python list **迁入 Postgres**。
3. MCP Server 暴露 **3 个原子工具**,LangGraph agent 侧用 `langchain-mcp-adapters` 作为 client 消费。
4. 同一个 server 同时支持 **stdio**(Claude Desktop 演示)和 **Streamable HTTP**(app 消费)两种传输。

### 非目标(明确延后到 M2/M3)

- LLM 自主选工具(tool-calling agent)——M1 节点仍以编程方式调用工具。
- Supervisor 编排、分诊 / 急诊预警 agent。
- Eval 工具与质量指标。

M1 只搭 MCP 管道 + 解耦知识层;原子工具的接口现在就为 M2 和 Claude Desktop demo 铺好路。

## 3. 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 传输方式 | **stdio + Streamable HTTP 都支持** | 一份 FastMCP 代码、启动参数切换。HTTP 给 app 干净的服务间调用,stdio 给 Claude Desktop 即插即用 demo。额外成本极小,作品集价值最高。 |
| 工具粒度 | **原子工具(primitives)** | 最能体现 agent 动态选工具(M2),且每个工具在 Claude Desktop 里可单独调用演示。 |
| 仓库关系 | **独立包 + 共享 Postgres** | 知识逻辑**迁移而非复制**到 MCP server,`app/rag/` 缩成 client,无重复代码,且进程 + 代码双重独立,「可独立部署」叙事真实。 |
| 疾病表 schema | **`symptoms text[]` + GIN 索引** | 数据量小(25 条),数组重叠算子过滤 + Python 算 Dice,够用且能展示 Postgres 数组/GIN,不必上规范化 join 表。 |

被否决的方案:

- MCP server `import app.rag.*`:进程独立但代码耦合,「独立服务」叙事打折,不能脱离 app 代码库部署。
- 抽出第三方共享核心库:三个包,对单人作品集过度设计(YAGNI)。

## 4. 架构与仓库布局

```
backend/
  app/                      # FastAPI agent(消费方)
    mcp_client.py           # 新增:MultiServerMCPClient 初始化
    rag/retriever.py        # 瘦身:编排原子工具调用 → 拼 context 字符串
    rag/__init__.py
    # knowledge_base.py / vector_store.py / embeddings.py 的逻辑迁入 medical_kb_mcp
  medical_kb_mcp/           # 新增:MCP server 包(独立进程,可独立部署)
    __init__.py
    server.py               # FastMCP 应用 + 3 个工具 + stdio/http 启动入口
    db.py                   # Postgres 疾病表访问(Dice 匹配)
    vectors.py              # pgvector + DashScope 嵌入(从 app/rag 迁入)
    models.py               # Disease ORM 模型
    config.py               # 自己的 pydantic-settings,读同一个 .env
    seed_diseases.py        # 从原 DISEASE_KNOWLEDGE 灌库
```

数据流:

```
diagnose 节点 ─┐
advise 节点  ─┤→ app/mcp_client (HTTP) ─┐
              │                          ├─► medical_kb_mcp ─► Postgres(diseases 表)
Claude Desktop ─(stdio)─────────────────┘                  └─► pgvector(guidelines 集合)
```

- MCP server **不 import `app`**,只共享 venv 和 `.env`(同一个 `DATABASE_URL`、同一个 DashScope key、同一个 embedding model)。
- MCP server 有自己的 `config.py`(pydantic-settings 读同一 `.env`),避免依赖 `app.config`。

## 5. MCP 工具契约(3 个原子工具)

返回全部用 Pydantic 模型,FastMCP 自动转 JSON Schema 暴露给 LLM。

| 工具 | 入参 | 返回 | 替代现有 |
|---|---|---|---|
| `search_diseases_by_symptoms` | `symptoms: list[str]`, `limit: int = 5` | `list[DiseaseMatch]` | `knowledge_base.search_by_symptoms`(Dice) |
| `get_disease_detail` | `name: str` | `DiseaseDetail \| None` | `knowledge_base.search_by_disease` |
| `search_guidelines` | `query: str`, `k: int = 3` | `list[GuidelineChunk]` | `vector_store.ainvoke` 向量检索 |

Pydantic 返回模型:

```
DiseaseMatch:   name, matched_symptoms: list[str], match_score: float, severity, description
DiseaseDetail:  name, description, treatment, when_to_see_doctor, severity, symptoms: list[str]
GuidelineChunk: text, score: float
```

## 6. Postgres 疾病表 schema + 迁移

```
diseases
  id                  uuid pk
  name                text unique
  symptoms            text[]        -- GIN 索引
  description         text
  treatment           text
  when_to_see_doctor  text
  severity            text
```

- 候选过滤用数组重叠算子 `symptoms && ARRAY[...]`(走 GIN 索引),再在 Python 里对小候选集算 Dice 系数 `2*|A∩B| / (|A|+|B|)`(保留现有 `knowledge_base.py` 评分逻辑)。
- 新增一个 **Alembic revision** 建表;`Disease` 模型放 `medical_kb_mcp/models.py`,Alembic env 导入它(单一 Alembic 链管理所有表)。
- `seed_diseases.py` 把现有 25 条 `DISEASE_KNOWLEDGE` 转成行(逻辑搬运,数据不丢),幂等(已存在则跳过)。
- guideline markdown 仍在 `backend/data/guidelines/`;pgvector 灌库逻辑(原 `vector_store.py`)迁入 `medical_kb_mcp/vectors.py`,首次启动时 ingest,集合非空则跳过(保留现有持久化检查)。

## 7. Agent 侧接入 + M1/M2 边界

- `app/mcp_client.py`:用 `langchain-mcp-adapters` 的 `MultiServerMCPClient` 连 HTTP MCP server;`main.py` lifespan 启动时建立连接、加载工具句柄。
- `app/rag/retriever.py` 瘦身成**客户端编排器**:
  - `retrieve_for_diagnosis(symptoms)` → 调 `search_diseases_by_symptoms` + `search_guidelines`,拼 `medical_context`。
  - `retrieve_for_advice(diseases, symptoms)` → 调 `get_disease_detail`(每个疾病)+ `search_guidelines`,拼 `medical_context`。
  - 拼装格式沿用现有 retriever 的 `【知识库匹配结果】/【医学文献参考】` 风格,**节点代码几乎不动**。
- **M1**:节点仍以编程方式调用工具(不是 LLM 自主选)。
- **M2(延后)**:节点升级为 tool-calling agent,LLM 自主决定调哪个工具。

## 8. 错误处理与优雅降级

- **MCP server**:每个工具内部捕获 DB/嵌入异常,返回空结果而非崩溃;`search_guidelines` 遇 DashScope 失败 → 返回 `[]` + 日志告警。
- **App 侧**:MCP 连接失败 → 沿用现有 `main.py` 的 try/except 降级模式,retriever 返回 `""`,图照常跑(无 RAG context),不阻断主流程。
- stdio(Claude Desktop)与 HTTP(app)互相独立,一边挂不影响另一边。

## 9. 测试策略

- **MCP server 单测**:三个工具对测试库 —— 已知症状组合命中预期疾病、精确查名返回详情、向量检索返回 chunk。
- **MCP 协议级测试**:起 server,用 mcp client `list_tools` + `call_tool`,校验工具 schema 与返回结构。
- **App 集成**:retriever 经 MCP 拼 context;server 不可用时降级为空字符串。
- **回归**:现有 `backend/tests/test_api.py` / `test_integration.py` 行为不变,应继续通过。

## 10. 依赖变更

新增到 `backend/requirements.txt`:

- `mcp`(官方 MCP Python SDK,含 FastMCP)—— MCP server 端。
- `langchain-mcp-adapters` —— app 端 MCP client。
- `dashscope` —— 当前 `embeddings.py` 已 import 但**未在 requirements.txt 声明**,迁入 MCP server 时显式补上。

复用现有:`langchain-postgres`(pgvector)、`asyncpg`/`psycopg`、`sqlalchemy`、`alembic`、`pydantic-settings`。

## 11. 风险与备注

- `text[]` + GIN 对 25 条数据是 over-kill 但展示价值高;若未来疾病量大增,Dice 评分可能需要下推到 SQL —— M1 不处理。
- stdio 子进程在 FastAPI 长驻服务中的生命周期较别扭,因此 **app 侧固定走 HTTP**,stdio 仅用于 Claude Desktop;两条路径共用同一份 server 代码。
- 单一 Alembic 链管理 `diseases` 表会让 MCP server 的 schema 演进依赖 app 的迁移目录 —— 为简化,M1 接受此轻度耦合。
