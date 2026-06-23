# 部署指南

## 技术栈

| 组件 | 技术 | 说明 |
|---|---|---|
| 前端 | Next.js 14 | React SSR |
| 后端 | FastAPI + Uvicorn | Python ASGI |
| 数据库 | PostgreSQL 17 + pgvector | 向量检索 |
| 缓存 | Redis 7.x | 可选，自动降级 |
| 认证 | Supabase | JWT 认证托管 |
| LLM | DashScope (qwen-plus) | 阿里云通义千问 |
| 代理 | Nginx | 反向代理 + SSE 支持 |

## Docker Compose 部署（推荐）

### 1. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
apt install docker-compose-plugin

# 验证
docker --version
docker compose version
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入实际的 API Key 和 Supabase 配置
nano .env
```

必须填写的项：
- `LLM_API_KEY` — DashScope API Key
- `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_JWT_SECRET` — Supabase 项目配置
- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` — 同上（前端用）
- `API_KEY` — 你的应用密钥（前端注入后端请求头）
- `POSTGRES_PASSWORD` — 数据库密码

### 3. 构建启动

```bash
docker compose up -d --build
```

### 4. 访问

| 地址 | 说明 |
|---|---|
| `http://服务器IP` | 通过 Nginx 访问（80 端口，推荐） |
| `http://服务器IP:3000` | 直接访问前端 |
| `http://服务器IP:8000` | 直接访问后端 API |

### 5. 常用命令

```bash
# 查看日志
docker compose logs -f backend
docker compose logs -f frontend

# 重启某个服务
docker compose restart backend

# 停止所有服务
docker compose down

# 停止并删除数据卷（⚠️ 会清空数据库）
docker compose down -v
```

### 6. 数据库迁移

```bash
# 进入后端容器执行 alembic 迁移
docker compose exec backend alembic upgrade head
```

## 架构图

```
用户浏览器
    │
    ▼
  Nginx (:80)
    ├── /         → frontend:3000 (Next.js SSR)
    └── /api/     → backend:8000 (FastAPI)
                        ├── db:5432 (PostgreSQL + pgvector)
                        └── redis:6379 (Redis)
```

## 目录结构

```
项目根目录/
├── docker-compose.yml       # 服务编排
├── .env                     # 环境变量（从 .env.example 复制）
├── nginx.conf               # Nginx 配置
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt
│   └── app/
└── frontend/
    ├── Dockerfile
    ├── .dockerignore
    ├── next.config.js       # output: 'standalone'
    └── src/
```

## HTTPS 配置（可选）

如需 HTTPS，推荐在 Nginx 前加一层 Cloudflare 或使用 certbot：

```bash
# 安装 certbot
apt install certbot python3-certbot-nginx

# 申请证书（需要域名已解析到服务器 IP）
certbot --nginx -d your-domain.com

# 自动续期
certbot renew --dry-run
```
