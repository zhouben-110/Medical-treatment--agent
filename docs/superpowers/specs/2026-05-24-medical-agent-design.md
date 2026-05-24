# 医疗Agent设计文档

## 概述

搭建一个个人健康助手Agent，用户描述症状后，AI通过多轮对话分析症状，最终给出治疗建议。

## 技术栈

- **前端**: Next.js
- **后端**: FastAPI
- **AI框架**: LangChain + LangGraph
- **数据库**: SQLite (MVP) / PostgreSQL (生产)

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端层 (Next.js)                      │
│         聊天界面 │ 历史记录 │ 症状分类                    │
└─────────────────────────────────────────────────────────┘
                          ↕ WebSocket / REST API
┌─────────────────────────────────────────────────────────┐
│                    API层 (FastAPI)                       │
│           /chat │ /history │ /symptoms                  │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│                   核心层 (LangGraph)                     │
│      症状分析 │ 追问决策 │ 疾病匹配 │ 建议输出            │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│                      数据层                              │
│            SQLite/PostgreSQL │ 对话历史                  │
└─────────────────────────────────────────────────────────┘
```

### LangGraph状态机

**流程:**
```
开始 → 接收症状 → 症状分析 → 信息完整?
                              ↓ 否      ↓ 是
                         追问节点    疾病匹配
                              ↓ 循环      ↓
                                   生成建议 → 结束
```

**状态定义:**
```python
{
    messages: List[Message]        # 对话历史
    symptoms: List[str]            # 提取的症状列表
    current_stage: str             # 当前阶段
    confidence: float              # 诊断置信度
    possible_diseases: List[str]   # 可能的疾病
    treatment_plan: str            # 治疗建议
    need_more_info: bool           # 是否需要更多信息
}
```

**核心节点:**
1. **症状分析节点** — 从用户描述中提取症状，识别关键信息
2. **追问决策节点** — 判断信息是否完整，决定追问内容
3. **疾病匹配节点** — 根据症状组合匹配可能的疾病
4. **建议输出节点** — 生成治疗建议和注意事项

## API接口设计

### POST /api/chat

发送消息，获取AI回复。

**请求:**
```json
{
    "message": "我最近总是头痛",
    "session_id": "optional-session-id"
}
```

**响应:**
```json
{
    "reply": "了解了。请问头痛持续多久了？",
    "stage": "questioning",
    "symptoms": ["头痛"]
}
```

### GET /api/history

获取用户历史对话列表。

**响应:**
```json
{
    "sessions": [
        {
            "id": "session-123",
            "title": "头痛发烧咨询",
            "created_at": "2026-05-24T10:00:00Z",
            "message_count": 6
        }
    ]
}
```

### GET /api/history/{session_id}

获取指定会话的详细记录。

**响应:**
```json
{
    "messages": [
        {
            "role": "user",
            "content": "我最近总是头痛",
            "timestamp": "2026-05-24T10:00:00Z"
        }
    ],
    "diagnosis": "紧张性头痛"
}
```

### GET /api/symptoms

获取症状分类列表。

**响应:**
```json
{
    "categories": [
        {
            "name": "头部",
            "symptoms": ["头痛", "头晕", "耳鸣"]
        }
    ]
}
```

## 数据模型

```sql
-- 用户表
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    diagnosis TEXT
);

-- 消息表
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    role TEXT CHECK(role IN ('user', 'assistant')),
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 症状分类表（预置数据）
CREATE TABLE symptom_categories (
    id TEXT PRIMARY KEY,
    name TEXT
);

-- 症状表（预置数据）
CREATE TABLE symptoms (
    id TEXT PRIMARY KEY,
    category_id TEXT REFERENCES symptom_categories(id),
    name TEXT
);
```

## 前端界面

### 页面布局

- **左侧边栏**: 新对话按钮 + 历史记录列表
- **右侧主区**: 消息展示区 + 输入框

### 关键交互

1. **流式输出** — AI回复逐字显示，提升用户体验
2. **症状高亮** — 识别出的症状用标签高亮显示
3. **加载状态** — 分析中显示loading动画

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| LLM调用失败 | 降级为预设回复，提示用户稍后重试 |
| 症状无法识别 | 引导用户重新描述，或建议就医 |
| 数据库连接失败 | 内存缓存兜底，异步重试写入 |

**免责声明**: 每次回复末尾附带"仅供参考，不构成医疗建议"

## 测试策略

- **单元测试** — 各节点逻辑独立测试
- **集成测试** — 完整对话流程测试
- **API测试** — 接口请求响应验证
- **E2E测试** — 前端到后端完整流程

## MVP范围

### 核心功能
- 症状描述 → 治疗建议（单轮）
- 多轮对话追问
- 历史记录保存
- 症状分类浏览

### 后续迭代
- RAG接入专业医学数据
- 更复杂的诊断逻辑
- 用户账户系统