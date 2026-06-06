# Medical-KB MCP Server

独立的医学知识 MCP 服务（独立进程，可独立部署）。把疾病结构化检索与诊疗指南向量检索抽成
3 个原子工具，经标准 MCP 协议对外提供。同一份代码同时支持 **stdio**（Claude Desktop 演示）
与 **Streamable HTTP**（FastAPI app 消费）两种传输。

## 工具（3 个原子工具）

| 工具 | 入参 | 返回 |
|---|---|---|
| `search_diseases_by_symptoms` | `symptoms: list[str]`, `limit: int = 5` | `list[DiseaseMatch]`（name / matched_symptoms / match_score / severity / description），按 Dice 相似度排序 |
| `get_disease_detail` | `name: str` | `DiseaseDetail \| None`（含 treatment / when_to_see_doctor / symptoms 等） |
| `search_guidelines` | `query: str`, `k: int = 3` | `list[GuidelineChunk]`（text / score），pgvector 语义检索 |

三个工具均为只读（`readOnlyHint`），内部捕获异常并降级为空结果，绝不让协议层崩溃。

## 运行

```bash
# Streamable HTTP（app 消费，默认 127.0.0.1:8765，端点 /mcp）
python -m medical_kb_mcp.server http

# stdio（Claude Desktop / 本地工具）
python -m medical_kb_mcp.server stdio
```

## 环境变量（读同一个 backend/.env）

- `DATABASE_URL` —— Postgres 连接串（`diseases` 表 + `medical_guidelines` 向量集合）。
- `LLM_API_KEY` —— DashScope key（`search_guidelines` 的嵌入需要）。
- `EMBEDDING_MODEL` —— 默认 `text-embedding-v3`。
- `MCP_HOST` / `MCP_PORT` —— HTTP 传输的监听地址，默认 `127.0.0.1:8765`。

## 前置数据

- 疾病表：`alembic upgrade head` 建表后 `python -m medical_kb_mcp.seed_diseases` 灌入 25 条（幂等）。
- 指南向量集合：M1 直接读取**已存在**的 `medical_guidelines` 集合；若库为全新空库，
  `search_guidelines` 会优雅降级为空（结构化疾病检索仍可用）。重新 ingest
  `data/guidelines/*.md` 为 M1 之后的跟进项。

## Claude Desktop 演示

1. 把仓库根目录的 `claude_desktop_config.example.json` 内容并入 Claude Desktop 的
   `claude_desktop_config.json`，把 `cwd` 改成本机 backend 绝对路径、填好 `DATABASE_URL`
   与 `LLM_API_KEY`。
2. 重启 Claude Desktop。
3. 直接对话即可触发工具，例如：「用发热、咳嗽、流涕帮我查可能的疾病」。
