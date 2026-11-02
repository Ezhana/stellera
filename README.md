# Stellera

多语言 monorepo：根目录只做编排——唯一入口是 [`just`](https://github.com/casey/just)，项目各自带工具链
（前端 pnpm workspace、后端 uv）。根目录没有 `package.json` / lockfile，也没有根级任务调度器或根级依赖安装：

| 项目 | 目录 | 工具链 | 说明 |
| --- | --- | --- | --- |
| `hub`（web） | `clients/web` | pnpm workspace（Node 24） | Vue 3 + Vite 前端工作区，应用在 `apps/hub`（Obsidian 黑金 FDE 交付控制台：平台简介 + 实时订单大厅，含 BFF/页面模型层） |
| `hub-api` | `services/python-hub-api` | uv（Python 3.13） | FastAPI + PostgreSQL，Authlib JWT 登录、pycasbin RBAC 与 FDE 订单/实时推送 |

本地全栈编排在 `infra/`（PostgreSQL + API + nginx 前端）；测试环境发布编排在 `deploy/`。

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

## 部署到测试环境（Docker Compose + just）

部署目标是**一台装了 Docker 的 Linux / macOS（或 Windows + Docker Desktop）主机**，由单机 Docker Compose
驱动，不引入 Kubernetes / Helm / 远程镜像仓库。宿主只负责按按钮：构建在 Dockerfile，就绪在 compose
healthcheck，配置校验在后端 Pydantic Settings，备份 / 恢复 / 迁移 / 冒烟都是镜像内的一次性 job。

首次部署（在测试机仓库根目录）：

```bash
git pull
cp deploy/env/staging.env.example deploy/env/staging.env   # 纯 KEY=VALUE 模板
just gen-secret 16        # 生成 POSTGRES_PASSWORD（32 位十六进制），填进 env
just gen-secret 32        # 生成 JWT_SECRET（64 位十六进制），填进 env
# 按需改 deploy/env/staging.env 的 WEB_PORT / CORS_ORIGINS / 镜像代理
mkdir -p deploy/.state/backups
just deploy staging
```

日常发布、回滚与运维：

```bash
git pull && just deploy staging                  # 构建带版本 tag 的镜像 → 备份 → up -d → 冒烟
just status staging                              # 容器 / 健康 / 实际在跑的镜像 tag
just logs staging -f api                         # 日志
just RELEASE_VERSION=<历史 tag> rollback staging  # 回滚（不重新构建）
just backup staging                              # 数据库备份
just restore staging <备份文件名>                  # 从备份恢复（危险操作）
just smoke staging                               # 冒烟测试（容器内跑）
```

默认入口 `http://<测试机>:8080`，登录页内置「测试环境演示账号」可一键填充；发布前自动备份数据库到
`deploy/.state/backups`。完整说明（配置项、回滚、备份保留策略、镜像代理、故障排查）见
[`deploy/README.md`](deploy/README.md)。

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

## 本地开发（热更新，just 入口）

环境要求：Python 3.13（见服务内 `.python-version`）、uv、Node.js 24（见 `clients/web/package.json` 的
`engines`；pnpm 由 corepack 按 `packageManager` 字段自动取用）、Docker（只用它的数据库）。

```bash
just backend-setup    # 起本地 db（infra/compose.yaml）→ uv sync → Alembic 迁移 → seed
just backend-serve    # 后端 http://127.0.0.1:8000（热更新，Swagger 在 /docs）

just frontend-install # 安装前端依赖
just frontend-dev     # 前端 Vite，默认 5173，/api 代理到 8000
```

也可以一条命令同时起前后端（Ctrl-C 一起退出；需要 POSIX shell：macOS/Linux/WSL/Git Bash）：

```bash
just dev
```

不经过 just 时，直接进各项目目录用自己的工具链也可以（等价能力）：

```bash
cd clients/web && pnpm install && pnpm dev
cd services/python-hub-api && cp .env.example .env && uv sync && uv run fastapi dev
```

## just 命令

`just` 是仓库唯一编排入口：只做薄壳转发，不承载业务逻辑（构建在 Dockerfile/CI，就绪在 compose
healthcheck，校验在后端 Settings，备份/恢复/迁移/冒烟在镜像内）。不带参数运行 `just` 会列出全部 recipe。

```bash
# 本地开发
just backend-setup / backend-serve / backend-lint / backend-fmt
just backend-typecheck / backend-test / backend-build
just frontend-install / frontend-dev / frontend-build / frontend-lint / frontend-typecheck
just dev                    # 前后端并行

# 发布（env 参数默认 staging，读取 deploy/env/<env>.env）
just deploy [env]           # build + 备份 + up -d + 冒烟
just rollback [env]         # 用 just RELEASE_VERSION=<tag> rollback 指定版本
just up / down / logs / status
just backup [env] [label]   # 数据库备份（保留天数在镜像内处理）
just restore [env] <file>   # 数据库恢复
just smoke / migrate / seed
just gen-secret [bytes]     # 生成随机十六进制密钥（一次性容器内生成）
```

帮助类 recipe 直接转发 compose，例如 `just status` 等价于
`docker compose -f deploy/docker-compose/compose.yaml --env-file deploy/env/staging.env ps`。

## 目录

```text
justfile                      # 根编排入口（薄壳转发，无业务逻辑）
clients/web/                  # 前端工作区：apps/hub、共享 ESLint/Prettier 配置
services/python-hub-api/      # 后端服务：app/、casbin/、migrations/、tests/
infra/                        # 本地 Docker 编排（前端 nginx 配置在 apps/hub）
deploy/                       # 测试环境发布编排：compose + ops 镜像 + env 模板
docs/adr/                     # 架构决策记录（0001 登录与 RBAC、0002 前端 BFF/页面模型、0003 FDE 订单）
tools/                        # 仓库级维护工具（gen-api 等，按需创建）
```

## CI

GitHub Actions 在 push / PR 时并行跑两个 job：后端 `services/python-hub-api` 用
`uv run ruff check` / `ruff format --check` / `uv run ty check app tests` / `uv run pytest` / `uv build`，
前端 `clients/web` 用 `pnpm lint` / `pnpm -r --if-present run test` / `pnpm build` / vue-tsc 类型检查。
没有根级安装步骤，也没有 affected 增量调度，见 [.github/workflows/ci.yml](.github/workflows/ci.yml)。

各目录的补充说明见 `clients/`、`services/`、`deploy/`、`infra/`、`tools/` 下的 README。
