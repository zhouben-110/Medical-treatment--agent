# 贡献指南

## 代码规范

### 后端 (Python)

- 使用 [ruff](https://docs.astral.sh/ruff/) 统一代码规范（配置见 `backend/pyproject.toml`）。
- 检查：`cd backend && ruff check .`
- 自动修复：`cd backend && ruff check . --fix`
- 安装：`pip install ruff`

### 前端 (Next.js)

- 使用 ESLint + `eslint-config-next`（配置见 `frontend/.eslintrc.json`）。
- 检查：`cd frontend && npm run lint`
- 依赖已声明于 `frontend/package.json`，全新克隆直接 `npm install` 即可。

### 换行符

仓库通过 `.gitattributes` 统一使用 LF，请勿在 Windows 上以 CRLF 提交。改动文件后可用
`git add --renormalize .` 校正。

## 提交信息规范

采用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

```
<type>(<scope>): <subject>
```

- `feat` 新功能
- `fix` 修复 bug
- `docs` 文档
- `refactor` 重构
- `test` 测试
- `chore` 杂项（构建/依赖）
- `perf` 性能优化

示例：

```
feat(kb): 新增知识库 MCP 检索接口
fix(triage): 修复空输入崩溃
docs: 更新 README 状态流转图
```

可选：`git config commit.template .gitmessage` 使用提交模板。

## 分支策略

- 功能开发在独立分支（如 `feat/xxx`），完成后合入 `master`。
- 临时 worktree 分支用完即删，不要残留到仓库。
