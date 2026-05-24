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
