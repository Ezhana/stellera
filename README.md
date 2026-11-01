# Stellera

多语言 monorepo：根目录只做编排（Nx 负责 target 缓存与顺序），项目各自带工具链。当前已接入 `clients/web`——Vue 3 + Vite 的前端工作区，Nx 项目名为 `web`。

## 用法

环境要求：Node.js 24（见 `clients/web/package.json` 的 `engines`）；pnpm 由 corepack 按 `packageManager` 字段自动取用，无需手动安装。

```bash
# 1. 安装前端工作区依赖（首次或 lockfile 变动后）
cd clients/web && pnpm install && cd ../..

# 2. 在根目录临时装一份 Nx（根目录按设计没有 package.json；生成物已被 .gitignore 忽略）
npm init --yes > /dev/null
npm install nx --no-fund --no-audit
```

常用命令（根目录执行）：

```bash
npx nx show projects             # 列出 Nx 项目，当前只有 web
npx nx run web:serve             # 本地开发，常驻进程
npx nx run web:build             # 构建，产物在 clients/web/apps/hub/dist
npx nx run web:lint              # 根 ESLint + 各 app 的 lint
npx nx run web:test              # 当前没有用例，正常空跑
npx nx run web:typecheck         # vue-tsc 类型检查
npx nx affected -t lint test build   # 只跑受影响项目
```

也可以不经过 Nx，直接在前端工作区里执行：

```bash
cd clients/web
pnpm dev                         # 开发
pnpm build                       # 构建
pnpm lint                        # lint
pnpm format:check                # 格式检查（pnpm format 可直接修复）
```

CI：GitHub Actions 在 push / PR 时先 `pnpm install --frozen-lockfile`，再跑 `nx affected -t lint test build`，见 [.github/workflows/ci.yml](.github/workflows/ci.yml)。各目录的补充说明见 `clients/`、`services/`、`deploy/`、`tools/` 下的 README。
