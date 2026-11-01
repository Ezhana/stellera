# Stellera

多语言 monorepo：根目录只做编排（Nx 负责 target 缓存与顺序），项目各自带工具链。当前已接入两个项目：

| Nx 项目 | 目录 | 说明 |
| --- | --- | --- |
| `web` | `clients/web` | Vue 3 + Vite 前端工作区，应用为 `apps/hub`（Obsidian 黑金 FDE 交付控制台：平台简介 + 实时订单大厅，含 BFF/页面模型层） |
| `python-hub-api` | `services/python-hub-api` | FastAPI + PostgreSQL，Authlib JWT 登录、pycasbin RBAC 与 FDE 订单/实时推送 |

本地全栈编排在 `infra/`（PostgreSQL + API + nginx 前端）。

## 一键本地启动（Docker）

环境要求：Docker + Docker Compose v2。

```bash
cp infra/.env.example infra/.env     # 至少改掉 JWT_SECRET
docker compose -f infra/compose.yaml up --build -d
docker compose -f infra/compose.yaml ps
```

| 地址 | 说明 |
| --- | --- |
| <http://localhost:8080/login> | 登录页（中文黑金商务风 / Obsidian） |
| <http://localhost:8080/intro> | 平台简介（轮播图 + 叙事；登录后的默认页） |
| <http://localhost:8080/fde/hall> | FDE 订单大厅（WebSocket 实时更新） |
| <http://localhost:8080/fde/published> | 我发布的（查看当前发布、发布新需求） |
| <http://localhost:8000/docs> | Swagger |
| <http://localhost:8000/health/ready> | API + DB 就绪检查 |

默认账号见 `infra/.env.example`：`admin` / `admin12345`（管理员，可代操作全部订单）。
`SEED_DEMO_USERS=true` 时另有企业演示账号 `enterprise` / `enterprise12345`、工程师演示账号
`engineer` / `engineer12345`，以及 `operator`、`viewer`。这些弱口令只用于本机开发。

## 部署到测试环境（Docker only）

测试环境用 `deploy/` 下的编排与脚本：在一台装了 Docker 的机器上 `git pull` 后一键完成
构建、备份、启动、健康检查与回滚，不依赖 Kubernetes / Helm / 私有镜像仓库。

```bash
git pull
deploy/scripts/init-env.sh --env staging        # 首次：生成 deploy/env/staging.env
deploy/scripts/deploy.sh --env staging          # 构建 + 发布 + 冒烟测试
```

默认入口 `http://<测试机>:8080`，登录页内置「测试环境演示账号」可一键填充；
发布前自动备份数据库到 `deploy/.state/backups`，回滚用 `deploy/scripts/rollback.sh --env staging`。
完整说明（配置项、回滚、备份恢复、镜像代理、故障排查）见 [`deploy/README.md`](deploy/README.md)。

## FDE 订单模块

业务闭环：**企业发布需求 → 平台代收并托管资金 → 工程师接单交付（提交工作日志）→ 企业验收 → 平台结算**。

- 左侧菜单为两级：`平台 → 平台简介`、`FDE 订单 → 订单大厅（实时）/ 我发布的`；钱包、广场等旧模块已暂时移除。
- 订单大厅列表展示任务、行业、交付周期、价格、状态、托管状态与发布时间，支持状态/行业/关键词筛选。
- 实时更新走 `WebSocket /api/v1/fde/ws`：创建、认领、日志、完成、取消都会广播
  `order.created` / `order.updated`，断线自动重连，刷新列表兜底。
- 后端 RBAC 在 `authenticated` 之上新增 `enterprise`（发布/完成/取消）与 `engineer`（认领/提交日志）角色；
  未认证请求由 Casbin 中间件返回 401/403。
- API 一览见 [`services/python-hub-api/README.md`](services/python-hub-api/README.md)，
  取舍记录见 [`docs/adr/0003-fde-orders.md`](docs/adr/0003-fde-orders.md)。

## 本地开发（热更新）

```bash
# 1. 只起数据库
docker compose -f infra/compose.yaml up -d db

# 2. 后端：http://127.0.0.1:8000
cd services/python-hub-api
cp .env.example .env                  # DATABASE_URL 指向 localhost
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run fastapi dev

# 3. 前端：Vite 默认 5173，/api 代理到 8000
cd clients/web
pnpm install
pnpm dev
```

环境要求：Python 3.13（见服务内 `.python-version`）、uv、Node.js 24（见 `clients/web/package.json` 的 `engines`）；pnpm 由 corepack 按 `packageManager` 字段自动取用。

## Nx 命令

根目录按设计没有 `package.json`，首次使用先临时装一份 Nx（生成物已被 `.gitignore` 忽略）：

```bash
npm init --yes > /dev/null
npm install nx --no-fund --no-audit
```

```bash
npx nx show projects                  # web, python-hub-api
npx nx run web:serve                  # 前端开发，常驻进程
npx nx run web:build                  # 前端构建，产物在 clients/web/apps/hub/dist
npx nx run web:lint                   # 根 ESLint + 各 app lint
npx nx run web:test                   # Vitest
npx nx run web:typecheck              # vue-tsc
npx nx run python-hub-api:lint        # ruff check + format check
npx nx run python-hub-api:test        # pytest（SQLite，不依赖 Docker）
npx nx run python-hub-api:typecheck   # ty
npx nx run python-hub-api:build       # uv build，产物在服务内 dist/
npx nx affected -t lint test build typecheck   # 只跑受影响项目
```

也可以不经过 Nx，直接在各项目里执行：

```bash
cd clients/web && pnpm dev / pnpm build / pnpm lint / pnpm format:check
cd services/python-hub-api && uv run pytest / uv run ruff check .
```

## 目录

```text
clients/web/                  # 前端工作区：apps/hub、共享 ESLint/Prettier 配置
services/python-hub-api/      # 后端服务：app/、casbin/、migrations/、tests/
infra/                        # 本地 Docker 编排（前端 nginx 配置在 apps/hub）
deploy/                       # 发布环境编排（staging/prod），与 infra 分工
docs/adr/                     # 架构决策记录（0001 登录与 RBAC、0002 前端 BFF/页面模型、0003 FDE 订单）
tools/                        # 仓库级维护工具（gen-api 等，按需创建）
```

## CI

GitHub Actions 在 push / PR 时安装前端 pnpm 依赖与后端 uv 依赖，再跑
`nx affected -t lint test build typecheck`，见 [.github/workflows/ci.yml](.github/workflows/ci.yml)。

各目录的补充说明见 `clients/`、`services/`、`deploy/`、`infra/`、`tools/` 下的 README。
