# Stellera

多语言 monorepo：根目录只做编排——唯一入口是 [`just`](https://github.com/casey/just)，项目各自带工具链
（前端 pnpm workspace、后端 uv）。根目录没有 `package.json` / lockfile，也没有根级任务调度器或根级依赖安装：

| 项目 | 目录 | 工具链 | 说明 |
| --- | --- | --- | --- |
| `hub`（web） | `clients/web` | pnpm workspace（Node 24） | Vue 3 + Vite 前端工作区，应用在 `apps/hub`（Obsidian 黑金 FDE 交付控制台：平台简介 + 实时订单大厅，含 BFF/页面模型层） |
| `hub-api` | `services/hub-api` | uv（Python 3.13） | FastAPI + PostgreSQL，Authlib JWT 登录、pycasbin RBAC 与 FDE 订单/实时推送 |

`infra/` 提供本地依赖（PostgreSQL、Redis、new-api）；`deploy/` 是单机发布编排：include `infra/`，
再追加 `hub-api` 与 `web` 两个应用镜像。

## 一键启动（Docker）

环境要求：Docker + Docker Compose v2。

```bash
cp deploy/.env.example deploy/.env
just gen-secret 16        # 生成 POSTGRES_PASSWORD，填进 deploy/.env
just gen-secret 32        # 生成 JWT_SECRET，填进 deploy/.env
just up                   # 构建 hub-api / web 镜像并后台启动全部服务
just ps
```

需要演示账号与订单时，把 `deploy/.env` 的 `INIT_ARGS` 设为 `--demo` 后重新 `just up`：会额外写入
`enterprise / engineer / operator / viewer` 演示账号与 10 条 FDE 演示订单。

| 地址 | 说明 |
| --- | --- |
| <http://localhost:8080/login> | 登录页（中文黑金商务风 / Obsidian） |
| <http://localhost:8080/intro> | 平台简介（轮播图 + 叙事；登录后的默认页） |
| <http://localhost:8080/fde/hall> | FDE 订单大厅（WebSocket 实时更新） |
| <http://localhost:8080/fde/published> | 我发布的（查看当前发布、发布新需求） |
| <http://localhost:3000> | new-api 控制台 |

管理员账号默认 `admin` / `admin12345`（`deploy/.env` 的 `ADMIN_*` 可改），只适合本机与测试环境。

## 部署到测试环境

部署目标是**一台装了 Docker 的 Linux / macOS（或 Windows + Docker Desktop）主机**，由单机 Docker Compose
驱动，不引入 Kubernetes / Helm / 远程镜像仓库：构建在 Dockerfile，就绪在 compose healthcheck，
数据库迁移与种子由一次性 `init` job 在启动时完成。

```bash
git pull
cp deploy/.env.example deploy/.env
just gen-secret 16        # POSTGRES_PASSWORD
just gen-secret 32        # JWT_SECRET
# 按需改 deploy/.env 的 WEB_PORT / CORS_ORIGINS / INIT_ARGS / 镜像与包源
just up
just ps
```

日常更新与排查：

```bash
git pull && just up         # 重新构建并后台重启
just logs -f api            # 日志：just logs -f web / just logs -f new-api
just restart api            # 只重启某个服务
just down                   # 停止并删除容器（数据卷保留）
```

默认入口 `http://<测试机>:8080`；PostgreSQL 数据在 compose 卷 `postgres_data`，
new-api 数据在 `infra/new-api/data`。

## FDE 订单模块

业务闭环：**企业发布需求 → 平台代收并托管资金 → 工程师接单交付（提交工作日志）→ 企业验收 → 平台结算**。

- 左侧菜单为两级：`平台 → 平台简介`、`FDE 订单 → 订单大厅（实时）/ 我发布的`；钱包、广场等旧模块已暂时移除。
- 订单大厅列表展示任务、行业、交付周期、价格、状态、托管状态与发布时间，支持状态/行业/关键词筛选。
- 实时更新走 `WebSocket /api/v1/fde/ws`：创建、认领、日志、完成、取消都会广播
  `order.created` / `order.updated`，断线自动重连，刷新列表兜底。
- 后端 RBAC 在 `authenticated` 之上新增 `enterprise`（发布/完成/取消）与 `engineer`（认领/提交日志）角色；
  未认证请求由 Casbin 中间件返回 401/403。
- API 一览见 [`services/hub-api/README.md`](services/hub-api/README.md)，
  取舍记录见 [`docs/adr/0003-fde-orders.md`](docs/adr/0003-fde-orders.md)。

## 本地开发（热更新）

环境要求：Python 3.13（见 `services/hub-api/.python-version`）、uv、Node.js 24（见 `clients/web/package.json`
的 `engines`；pnpm 由 corepack 按 `packageManager` 字段自动取用）、Docker（只用它的数据库）。

```bash
# 本地依赖：PostgreSQL（含 new-api、hub 两个库）+ Redis + new-api
cp infra/.env.example infra/.env
docker compose -f infra/compose.yaml up -d
```

后端：<http://127.0.0.1:8000>（热更新，Swagger 在 `/docs`）。`DATABASE_URL` 的用户名/密码
要与 `infra/.env` 一致（默认 `stellera` / `stellera`）。

```bash
cd services/hub-api
cp .env.example .env          # 按 infra/.env 改 DATABASE_URL
uv sync
uv run python -m app.scripts.init --demo
uv run fastapi dev
```

前端：<http://127.0.0.1:5173>，`/api` 代理到 8000。

```bash
cd clients/web
pnpm install && pnpm dev
```

## just 命令

`just` 是仓库唯一编排入口：只做薄壳转发，部署编排在 `deploy/compose.yaml`。不带参数运行 `just` 会列出全部 recipe。

```bash
just up [service...]        # 构建镜像并后台启动（不带参数=全部；如 just up api）
just down                   # 停止并删除容器（保留数据卷）
just restart [service...]   # 重启服务
just logs [args...]         # 日志：just logs -f api / just logs -f web
just ps                     # 容器 / 健康状态
just build [service...]     # 只构建镜像
just gen-secret [bytes]     # 生成随机十六进制密钥（默认 32 字节）
```

帮助类 recipe 直接转发 compose，例如 `just ps` 等价于
`docker compose -f deploy/compose.yaml --env-file deploy/.env ps`。

## 目录

```text
justfile                      # 根编排入口（薄壳转发，无业务逻辑）
clients/web/                  # 前端工作区：apps/hub、共享 ESLint/Prettier 配置、通用 Dockerfile
services/hub-api/             # 后端服务：app/、casbin/、migrations/、tests/
infra/                        # 本地依赖编排：postgres/、redis、new-api/
deploy/                       # 发布编排：compose.yaml（include infra + hub-api/web）与 .env.example
docs/adr/                     # 架构决策记录（0001 登录与 RBAC、0002 前端 BFF/页面模型、0003 FDE 订单）
tools/                        # 仓库级维护工具（gen-api 等，按需创建）
```

## CI

GitHub Actions 在 push / PR 时并行跑两个 job：后端 `services/hub-api` 用
`uv run ruff check` / `ruff format --check` / `uv run ty check app tests` / `uv run pytest` / `uv build`，
前端 `clients/web` 用 `pnpm lint` / `pnpm -r --if-present run test` / `pnpm build` / vue-tsc 类型检查。
没有根级安装步骤，也没有 affected 增量调度，见 [.github/workflows/ci.yml](.github/workflows/ci.yml)。

各子项目的补充说明见其目录下的 README（如 `services/hub-api`、`clients/web`）。
