# 部署指南 - Vercel + Railway

## 前置准备

### 1. 注册账号
- [Vercel](https://vercel.com) - 前端托管（免费）
- [Railway](https://railway.app) - 后端托管（免费 500h/月）
- [GitHub](https://github.com) - 代码仓库

### 2. 安装 CLI 工具
```bash
# Vercel CLI
npm i -g vercel

# Railway CLI
npm i -g @railway/cli
```

---

## 第一步：推送代码到 GitHub

```bash
cd C:\Users\Administrator\Desktop\医疗agent

# 初始化 git（如果还没有）
git init
git add .
git commit -m "准备部署"

# 创建 GitHub 仓库后推送
git remote add origin https://github.com/你的用户名/medical-agent.git
git push -u origin master
```

---

## 第二步：部署后端到 Railway

### 2.1 创建 Railway 项目
1. 打开 https://railway.app
2. 点击 **New Project** → **Deploy from GitHub Repo**
3. 选择你的 `medical-agent` 仓库
4. Railway 会自动检测到 `Procfile` 和 `nixpacks.toml`

### 2.2 添加 PostgreSQL 数据库
1. 在 Railway 项目中点击 **New** → **Database** → **PostgreSQL**
2. 等待数据库创建完成
3. 点击数据库 → **Connect** → 复制 `DATABASE_URL`

### 2.3 添加 Redis（可选）
1. 点击 **New** → **Database** → **Redis**
2. 复制 `REDIS_URL`

### 2.4 配置环境变量
在后端服务的 **Variables** 中添加：

| 变量名 | 值 |
|---|---|
| `LLM_API_KEY` | 你的 DashScope API Key |
| `DATABASE_URL` | Railway PostgreSQL 的 DATABASE_URL |
| `API_KEY` | 自定义一个强密码，如 `sk-medical-agent-2024` |
| `SUPABASE_URL` | 你的 Supabase 项目 URL |
| `SUPABASE_ANON_KEY` | 你的 Supabase Anon Key |
| `SUPABASE_JWT_SECRET` | 你的 Supabase JWT Secret |
| `CORS_ORIGINS` | `https://你的前端域名.vercel.app` |
| `REDIS_URL` | Railway Redis 的 REDIS_URL（可选） |

### 2.5 运行数据库迁移
Railway 部署完成后，进入后端服务的 **Deployments** → 点击最新部署 → **View Logs** 确认启动成功。

然后在 Railway 的 **Settings** → **Deploy** 中添加部署后命令：
```
cd backend && alembic upgrade head && python -m medical_kb_mcp.seed_diseases && python -m medical_kb_mcp.seed_guidelines
```

### 2.6 获取后端 URL
部署成功后，Railway 会分配一个域名，如：
```
https://medical-agent-production-xxxx.up.railway.app
```
记下这个 URL，后面要用。

---

## 第三步：部署前端到 Vercel

### 3.1 连接 GitHub 仓库
1. 打开 https://vercel.com
2. 点击 **Add New** → **Project**
3. 选择你的 `medical-agent` 仓库
4. **Root Directory** 设置为 `frontend`
5. **Framework Preset** 自动检测为 Next.js

### 3.2 配置环境变量
在 **Environment Variables** 中添加：

| 变量名 | 值 |
|---|---|
| `API_KEY` | 与后端相同的 API Key |
| `NEXT_PUBLIC_SUPABASE_URL` | 你的 Supabase 项目 URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | 你的 Supabase Anon Key |
| `BACKEND_URL` | Railway 后端的 URL（如 `https://medical-agent-production-xxxx.up.railway.app`） |

### 3.3 部署
点击 **Deploy**，等待构建完成。

部署成功后，Vercel 会分配一个域名，如：
```
https://medical-agent-xxxx.vercel.app
```

---

## 第四步：更新 CORS 配置

回到 Railway，更新后端的 `CORS_ORIGINS` 环境变量为 Vercel 的实际域名：
```
CORS_ORIGINS=https://medical-agent-xxxx.vercel.app
```

---

## 第五步：验证部署

1. 打开 Vercel 域名（如 `https://medical-agent-xxxx.vercel.app`）
2. 注册/登录账号
3. 测试聊天功能

---

## 常见问题

### Q: 后端启动失败？
检查 Railway 日志，常见原因：
- `DATABASE_URL` 格式错误
- `pgvector` 扩展未安装（Railway PostgreSQL 默认支持）
- 环境变量未设置

### Q: 前端无法连接后端？
- 确认 `BACKEND_URL` 正确
- 确认后端 `CORS_ORIGINS` 包含前端域名
- 检查 Railway 后端是否正常运行

### Q: Supabase 认证失败？
- 确认 `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_JWT_SECRET` 正确
- 在 Supabase Dashboard → Authentication → URL Configuration 中添加 Vercel 域名

---

## 自定义域名（可选）

### Vercel 自定义域名
1. Vercel 项目 → **Settings** → **Domains**
2. 添加你的域名，按提示配置 DNS

### Railway 自定义域名
1. Railway 服务 → **Settings** → **Networking**
2. 点击 **Generate Domain** 或添加自定义域名
