# Supabase Auth 配置指南

## 1. 创建 Supabase 项目

1. 访问 [supabase.com](https://supabase.com) 并注册/登录
2. 点击 "New Project" 创建新项目
3. 选择组织和区域，设置数据库密码
4. 等待项目创建完成

## 2. 获取配置信息

在 Supabase Dashboard 中：

1. 进入 **Settings** > **API**
2. 复制以下信息：
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_ANON_KEY`
   - **JWT Secret** → `SUPABASE_JWT_SECRET`

## 3. 配置环境变量

### 后端 (backend/.env)

```env
# Supabase 配置
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_JWT_SECRET=your-jwt-secret-here
```

### 前端 (frontend/.env.local)

```env
# Supabase 配置
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

## 4. 配置 Supabase 认证设置（可选）

在 Supabase Dashboard > **Authentication** > **Providers** 中：

1. **Email** - 默认启用，可配置：
   - 确认邮件模板
   - 密码重置邮件模板
   - 是否需要邮箱验证

2. **第三方登录**（可选）：
   - Google
   - GitHub
   - 其他 OAuth 提供商

## 5. 运行数据库迁移

```bash
cd backend
python -m alembic upgrade head
```

## 6. 启动应用

```bash
# 后端
cd backend
python start.py

# 前端
cd frontend
npm run dev
```

## 使用流程

1. 访问 `http://localhost:3000/register` 注册新账户
2. 检查邮箱进行验证（如果启用了邮箱验证）
3. 访问 `http://localhost:3000/login` 登录
4. 登录后即可使用医疗助手功能

## API 认证

所有需要认证的 API 端点都使用 Bearer Token：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "我头痛"}'
```

## 安全注意事项

1. **JWT Secret** - 仅在后端使用，不要暴露到前端
2. **anon key** - 可以公开使用，但配合 RLS 保护数据
3. **邮箱验证** - 生产环境建议启用
4. **密码策略** - Supabase 默认要求至少 6 位密码
5. **Rate Limiting** - 已内置登录接口限流

## 故障排除

### Token 验证失败

检查 `SUPABASE_JWT_SECRET` 是否正确配置。

### 前端无法登录

检查 `NEXT_PUBLIC_SUPABASE_URL` 和 `NEXT_PUBLIC_SUPABASE_ANON_KEY` 是否正确。

### 数据库迁移失败

确保数据库连接正常，然后重新运行：
```bash
python -m alembic upgrade head
```
