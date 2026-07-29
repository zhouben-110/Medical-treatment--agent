# 🩺 医疗健康助手 (Medical Agent)

AI 驱动的多 Agent 症状分析与健康咨询系统。系统基于 **LangGraph Supervisor** 模式实现多 Agent 协同，知识检索层采用进程内直接调用（零 IPC 开销），同时保留 **Model Context Protocol (MCP)** 接口用于外部集成（如 Claude Desktop），并基于 **pgvector (PostgreSQL)** 实现高精度的混合 RAG 检索，同时内置多维度的医疗用药安全红线拦截与生产级容灾防护。

---

## 🌟 核心特性

### 🤖 1. 多 Agent 协同编排 (LangGraph)
采用 Supervisor 集中编排模式，将问诊拆分为四大原子 Agent 节点：
* **急诊分诊 (Triage)**：前置 29 个红旗关键词零延迟过滤，结合 LLM 进行结构化急症判定，高危症状即刻触发 120 呼叫提示。
* **症状提取 (Symptom Analyzer)**：基于 Pydantic 提取结构化症状，自动进行实体合并与排重，支持前端标签化交互修改。
* **精准追问 (Questioner)**：根据现有症状库，自动追问持续时间、伴随症状、病史与过敏史，追问上限设为 5 轮，平衡体验与精度。
* **诊断报告**：提供两种实现，由 `ENABLE_AGENT_DIAGNOSE` 配置项二选一：
  * **固定管线 (Diagnose & Advise)**：按"先查疾病 → 再查详情"顺序硬编码检索，单次 LLM 出报告。延迟低、可预测，适合稳定复现。
  * **自主 Agent (Diagnose Agent)**：将 RAG 检索暴露为 4 个 LangChain 工具（`search_diseases` / `get_disease_detail` / `search_guidelines` / `submit_diagnosis`），由 LLM 自主决定调用顺序与次数，受 5 轮迭代 + 45s 墙钟预算约束。检索策略随病情自适应（如不典型症状时自动追加指南核查），但延迟与方差会上升。两条管线可在线 A/B 对比（见 `evals/`）。

### 📚 2. 知识检索服务
提供独立的 `medical_kb_mcp` 包，解耦核心知识层：
* **三个原子工具**：提供疾病匹配 (`search_diseases_by_symptoms`)、疾病详情 (`get_disease_detail`) 及指南语义检索 (`search_guidelines`)。
* **进程内直接调用**：FastAPI 后端通过 `app/services/kb_service.py` 直接导入并调用上述函数，共享数据库连接池，零 IPC 开销。
* **MCP 接口保留**：`medical_kb_mcp` 同时挂载为 MCP Server，支持 Claude Desktop（stdio 模式）等外部 MCP 客户端集成。

### 🔍 3. RAG 检索算法优化
* **密集与稀疏混合重排**：结合 pgvector 的 Cosine 相似度（占比 60%）和基于症状交集的 Dice 重叠系数（占比 40%）混合打分，兼顾语义理解与精准匹配。
* **元数据拼接前置**：在向量写入前将文档标题与段落拼接（`来自《...》：...`），解决独立切片丢失疾病主语的缺陷。
* **数据高保真**：去除了知识检索层对治疗详情和文献切片长度的硬性限制，确保 LLM 诊断能获取无损高保真的医学参考。

### 🧠 自主诊断 Agent 设计与边界
诊断 Agent 路径在「认知层」给 LLM 自主权，在「安全层」保持确定性：

* **自主部分**（LLM 决定）：调用哪些知识库工具、按什么顺序、调几次。这是规则写不完的——症状典型时一次 `search_diseases` 足矣，不典型时需追加 `search_guidelines` 核查。
* **确定部分**（代码强制）：① Triage 红旗匹配仍在前置短路，不允许模型自行判断是否紧急；② `submit_diagnosis` 工具被调用时，`finalize` 节点基于 `RETRIEVAL_TOOL_NAMES` 精确校验 `tool_trace` 是否包含有效检索调用，**无依据时直接走兜底文案**，拒绝凭记忆作答；③ `safety_rules` 在最终输出后置扫描用药禁忌，不依赖模型自觉。
* **资源约束**：最多 5 轮工具调用 + 45 秒墙钟预算，超限强制收口。
* **审计留痕**：`tool_trace` 字段持久化每次工具调用名、入参、返回值摘要，可复现"当时喂给 LLM 的是哪几条知识库记录"。
* **scratchpad 隔离**：Agent 内部工具调用轨迹不进 `messages`，避免污染用户对话历史与摘要逻辑。

### 🌊 节点级真流式 (SSE)
`/api/chat/stream` 走 LangGraph `astream(stream_mode="updates")`，每跑完一个节点立即向前端推送事件，**不再有"等 10 秒突然蹦字"**：

| 事件类型 | 含义 | 触发时机 |
|---|---|---|
| `meta` | 会话 ID / 末轮完整 state | 首帧 + 末帧各一次 |
| `status` | 阶段提示（"正在分诊" / "正在分析症状" / "正在生成追问" / "正在生成诊断"） | 进入关键节点时 |
| `chunk` | AI 回复文本 | 用户面节点（`diagnose` / `question` / `finalize` / `triage`）产生输出时整段 yield |
| `stage` | 当前阶段（`completed` / `emergency` / `questioning`） | 图结束时 |
| `tool` | Agent 调用的工具名与参数 | Agent 路径下 `on_tool_start` |
| `done` / `error` | 终止信号 | 末尾 |

**当前实现是节点级流式**，不是 token 级：LLM 内部仍走 `chain.ainvoke` 一次性返回，由 astream 在节点完成时把完整文本转成 `chunk` 事件。支持急诊短路提示即时输出与 Postgres 数据库自动归档持久化。

### 🛡️ 4. 生产级安全与合规
* **用药安全红线**：根据患者的年龄、孕产哺乳状态及过敏史，利用用药禁忌拦截器进行二次过滤，对不适用药物与过敏源输出醒目的强警示。
* **全生命周期防护**：前置 Prompt 注入防护；敏感日志脫敏；数据库凭据解耦；测试 Token 生产环境隔离禁封（防越权后门）。
* **双层鉴权**：本地 JWT (HS256) 与 API Key 双鉴权机制，实现 Session 级别的用户数据隔离。

### ⚡ 5. 高性能与优雅降级
* **二级缓存机制**：Redis 分层缓存诊断与检索结果；在 Redis 故障时，系统自动优雅降级为本地内存缓存（LRU 策略）。
* **IP 级滑动窗口限流**：支持基于 IP 维度的 Redis 滑动窗口限流（带 UUID 唯一成员防护），Redis 宕机时自动退化为内存级限流。
* **连接自愈与多级容灾**：数据库支持 `pool_pre_ping` 与 `pool_recycle` 自愈重连；LLM 客户端集成动态 API Key 随机轮询与 LangChain 原生 `with_fallbacks` 灾备模型自动切换。
* **异步 Checkpoint 管理**：全链路采用 LangGraph 原生 `aupdate_state` 异步状态管理，彻底消除跨线程同步阻塞与状态丢失。
* **向量检索索引优化**：系统启动时自动检测并在 pgvector `diseases` 向量列上按需构建 `HNSW` 空间索引，将检索复杂度从 $O(N)$ 降至 $O(\log N)$，极大降低高并发下的数据库 CPU 负载。
* **测试连接隔离**：测试环境自动切换为 `NullPool` 以规避 asyncpg 跨事件循环复用异常，并在 conftest 中自动注入 `vector` 扩展。
* **全链路日志可观测**：节点与检索层全面应用标准异步 `logging` 报错堆栈记录，杜绝历史 `print` 混用和解析异常时“默默吞错”的缺陷。

### 🗃️ 6. 动态知识库管理平台 (KB Management)
* **疾病库 CRUD**：支持对疾病条目、典型症状、就医指征的在线增删改查。症状更新时自动重算 1024 维语义特征向量。
* **指南自动切片导入**：支持长篇诊疗指南导入，以段落（`\n\n`）为粒度自动切片并提取来源元数据进行批量向量化写入。
* **RAG 检索评测沙箱**：在管理后台提供测试界面，直观比对和调试 Cosine 语义相关性分值与 Dice 症状重叠系数。

---

## 🛠️ 技术栈

* **后端**：FastAPI / SQLAlchemy 2.x + asyncpg / Alembic / LangGraph (Supervisor) / Uvicorn
* **AI & RAG**：DashScope (qwen-plus & text-embedding-v3) / pgvector 0.8.0 / MCP (Model Context Protocol)
* **缓存限流**：Redis 5.x / 7.x
* **前端**：Next.js 14 (App Router) / React 18 + TypeScript / Tailwind CSS / Server-Sent Events (SSE)

---

## 🚀 快速开始

### 1. 数据库准备 (PostgreSQL)
确保 PostgreSQL 已安装且开启了 `pgvector` 插件：
```sql
CREATE DATABASE medical_agent;
\c medical_agent
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. 后端启动
```bash
cd backend
# 安装依赖
pip install -r requirements.txt
# 配置文件 (填入 DashScope API Key, JWT 密钥等)
cp .env.example .env
# 数据库迁移
alembic upgrade head
# 灌入 25 种疾病种子数据 (自动计算并写入 embedding)
python -m medical_kb_mcp.seed_diseases
# 启动服务
python start.py
```
> 后端启动后将运行在 `http://localhost:8000`，可通过 `/health` 验证状态，在 `/docs` 查看交互式 Swagger 文档。

### 3. 前端启动
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```
> 访问 `http://localhost:3000` 即可开始问诊体验。

### 4. 挂载 Claude Desktop (可选)
复制 `claude_desktop_config.example.json` 内容至 Claude Desktop 配置中，将路径替换为绝对路径即可让 Claude 拥有本地医学库检索能力。详情参考：[MCP Server 运行指南](backend/medical_kb_mcp/README.md)。

---

## 🔀 系统架构与工作流

### 架构拓扑
```mermaid
graph LR
    User([用户]) <--> NextJS[Next.js 前端]
    NextJS <--> FastAPI[FastAPI 后端]
    subgraph FastAPI_Backend ["FastAPI 后端"]
        LangGraph[LangGraph 状态机] --> Retriever[RAG Retriever]
        Retriever --> KB["kb_service (直接调用)"]
        Redis[("Redis 缓存/限流")]
    end
    subgraph Knowledge_Layer ["知识层 (medical_kb_mcp)"]
        KB --> DB[("PostgreSQL + pgvector")]
        MCPServer[MCP Server] --> DB
    end
    MCPServer -.->|"外部集成 (Claude Desktop)"| EXT[外部 MCP 客户端]
```
### 状态流转图 (LangGraph 节点与路由映射)
```mermaid
stateDiagram-v2
    direction TB

    [*] --> supervisor : 用户发送消息

    state "supervisor 节点 (路由决策)" as supervisor {
        [*] --> CheckStage
        CheckStage --> RedFlagCheck : stage == "start"
        RedFlagCheck --> RouteEmergency : 命中红旗关键词
        RedFlagCheck --> RouteTriage : 未命中关键词
        
        CheckStage --> RouteAnalyze : stage == "triaged"
        CheckStage --> LLMDecision : stage == "analyzing"
        
        state LLMDecision <<choice>>
        LLMDecision --> RouteQuestion : need_more_info = true 且 轮次 < 5
        LLMDecision --> RouteDiagnose : need_more_info = false 或 轮次 ≥ 5
        
        CheckStage --> RouteDiagnose : stage == "questioning"
    }

    state "triage 节点 (分诊短路)" as triage {
        [*] --> Layer1_RedFlag
        Layer1_RedFlag --> EmergencyOut : 命中红旗关键词
        Layer1_RedFlag --> Layer2_LLMTriage : 未命中
        Layer2_LLMTriage --> EmergencyOut : is_emergency = true
        Layer2_LLMTriage --> TriagedOut : is_emergency = false
    }

    state "analyze 节点 (症状与画像提取)" as analyze {
        [*] --> PydanticExtract : SymptomExtraction
        PydanticExtract --> UpdateState : 提取 symptoms / severity / patient_profile
    }

    state "question 节点 (精准追问)" as question {
        [*] --> GenerateQuestion : 生成 1-3 个针对性问题，更新 stage = "questioning"
    }

    state "诊断管线 (由 ENABLE_AGENT_DIAGNOSE 决定路线)" as DiagnoseBranch {
        state "diagnose 节点 (固定管线)" as diagnose {
            [*] --> CheckCache
            CheckCache --> RAGRetrieve : 缓存未命中 (60% Cosine + 40% Dice)
            RAGRetrieve --> SingleLLM : 诊断 + 建议单次 LLM
            SingleLLM --> SafetyRules1 : intercept_contraindications 用药拦截
        }

        state "自主 Agent 子图 (ENABLE_AGENT_DIAGNOSE=true)" as AgentSubGraph {
            state "diagnose_agent 节点" as diagnose_agent {
                [*] --> LLMDecideTool : 绑定 KB_TOOLS 工具集
            }
            
            state "tools 节点 (ToolNode)" as tools {
                [*] --> ExecKBTool : 执行 search_diseases / get_disease_detail / search_guidelines
                ExecKBTool --> RecordTrace : 记录到 tool_trace 与 scratchpad
            }

            state "finalize 节点" as finalize {
                [*] --> VerifyTrace : 校验 RETRIEVAL_TOOL_NAMES
                VerifyTrace --> FallbackNoEvidence : 无检索依据 (防幻觉短路)
                VerifyTrace --> FormatSubmission : 有有效检索依据
                FormatSubmission --> SafetyRules2 : intercept_contraindications 用药拦截
            }

            diagnose_agent --> tools : route_after_agent (需要工具调用)
            tools --> diagnose_agent : 工具结果返回
            diagnose_agent --> finalize : route_after_agent (调用 submit_diagnosis / 5 轮上限 / 45s 超时)
        }
    }

    supervisor --> triage : route_after_supervisor -> triage
    supervisor --> END : route_after_supervisor -> finish (急诊短路 / 图结束)
    
    triage --> END : route_after_triage -> emergency (即刻输出 120 呼叫提示)
    triage --> supervisor : route_after_triage -> continue (设置 stage = "triaged")

    supervisor --> analyze : route_after_supervisor -> analyze
    analyze --> supervisor : 设置 stage = "analyzing" -> 回 supervisor 决策

    supervisor --> question : route_after_supervisor -> question
    question --> END : 设置 stage = "questioning" (等待用户下一轮回复)

    supervisor --> diagnose : route_after_supervisor -> diagnose (固定管线)
    supervisor --> diagnose_agent : route_after_supervisor -> diagnose_agent (自主 Agent)

    diagnose --> END : 设置 stage = "completed"
    finalize --> END : 清空 scratchpad，设置 stage = "completed"

    note right of supervisor
      诊断完成后 (stage == "completed")：
      用户继续发送新消息时，系统由 _reset_context_if_needed 摘要旧对话，
      保留历史症状与诊断结论，并将 stage 重置为 "start" 开启新一轮问诊。
    end note
```
###  项目效果

<img width="2219" height="1179" alt="Image" src="https://github.com/user-attachments/assets/6ae69600-04b0-4b80-85b4-3d396d916374" />
<img width="2474" height="1128" alt="Image" src="https://github.com/user-attachments/assets/682f164d-608a-444c-a0d9-520382a12a36" />
<img width="2514" height="1204" alt="Image" src="https://github.com/user-attachments/assets/f433d9fc-3a71-4379-aa18-fed72327f43d" />

## 📊 自动化评测 (E2E & CI)

系统自带了一套评测引擎，内置 35 个真实问诊 Case，支持 Mock 模式（用于 CI）和 Real 模式（调用真实模型与 DB 评估）。Real 模式可指定诊断管线（`fixed` / `agent`）做 A/B 对比。

```bash
cd backend
# 单测（含 mock eval）
python -m pytest evals/test_eval.py -v -s

# 程序化入口：固定管线
python -c "from evals.runner import run_eval; import asyncio; print(asyncio.run(run_eval('real','fixed')).format_report())"

# 程序化入口：自主 Agent 管线
python -c "from evals.runner import run_eval; import asyncio; print(asyncio.run(run_eval('real','agent')).format_report())"
```

### 核心评估指标
* 🎯 **诊断命中率** (目标 ≥60%，当前 **92.0%**)：Top-3 结果中是否包含目标疾病。
* 🔄 **平均追问轮数** (目标 <3.0，当前 **0.7 轮**)：到达诊断阶段前，Questioner 节点执行的平均次数。
* 🚨 **急症召回率** (目标 100%，当前 **100.0%**)：急症患者被正确分类为紧急的比例。
* 🔍 **急症精确度** (目标 100%，当前 **100.0%**)：被分类为紧急的患者中，真正属于急症的比例。

---

## 📂 项目结构

```
.
├── 知识库设计.md               # 动态知识库管理与 RAG 架构设计文档
├── backend/
│   ├── app/                    # FastAPI 核心业务代码
│   │   ├── nodes/              # LangGraph Agent 节点 (Triage/Analyze/Questioner/Diagnose + 自主诊断 Agent)
│   │   ├── tools/              # 自主诊断 Agent 的 LangChain 工具集 (4 个 @tool)
│   │   ├── routers/            # API 端点 (问诊、历史、用户管理、知识库管理 kb.py)
│   │   ├── services/           # 业务服务层 (kb_service 直接调用知识库，零 IPC 开销)
│   │   ├── rag/                # RAG 检索编排层
│   │   ├── safety_rules.py     # 用药安全校验拦截器
│   │   └── security.py         # Prompt 注入防护与安全净化
│   ├── medical_kb_mcp/         # 独立 MCP Server (含 pgvector 疾病/指南检索逻辑)
│   ├── evals/                  # 评测用例集与运行引擎
│   ├── alembic/                # 数据库迁移脚本
│   ├── data/guidelines/        # 诊疗指南 Markdown 数据源
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js 页面与路由 (包含 /admin/kb 知识库管理面板)
│   │   ├── components/         # 问诊状态机 UI 组件 (进度指示、症状更正标签)
│   │   ├── api/                # 前端 API 客户端 (client.ts & kb.ts)
│   └── next.config.js
└── docker-compose.yml           # 一键集成部署配置
```
