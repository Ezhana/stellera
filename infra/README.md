# infra/

Stellera Hub 的本地开发/演示基础设施：PostgreSQL + FastAPI 后端 + nginx 托管的前端，一条 `docker compose` 命令起全栈。

> 这里是**本地**编排。面向 staging/prod 的发布编排、K8s/Helm 与密钥管理仍在 `deploy/`，两者不重复。

## 前置条件

- Docker + Docker Compose v2（已验证 Docker 29 / Compose v5）
- 端口 `5432`、`8000`、`8080` 空闲；被占用时在 `.env` 改 `POSTGRES_PORT` / `API_PORT` / `WEB_PORT`

## 一键启动

```bash
cp .env.example .env
# 至少改掉 JWT_SECRET；演示账号密码也在 .env 里
docker compose up --build -d
docker compose ps
```

启动后：

| 地址 | 说明 |
| --- | --- |
| <http://localhost:8080/login> | 登录页（Obsidian 黑金风格） |
| <http://localhost:8080/intro> | 平台简介（轮播图 + 叙事，登录后默认页） |
| <http://localhost:8080/fde/hall> | FDE 订单大厅（WebSocket 实时更新） |
| <http://localhost:8080/fde/published> | 我发布的（发布需求入口） |
| <http://localhost:8000/docs> | FastAPI Swagger |
| <http://localhost:8000/health/ready> | API + DB 就绪检查 |

默认账号（来自 `.env.example`）：

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `admin12345` | admin（全部 `/api/v1/*`，可代操作订单） |
| `enterprise` | `enterprise12345` | enterprise（发布需求 / 完成 / 取消） |
| `engineer` | `engineer12345` | engineer（认领订单 / 提交工作日志） |
| `operator` | `operator12345` | operator（平台运营角色，可查看订单大厅） |
| `viewer` | `viewer12345` | viewer（只读，可查看订单大厅） |

`operator` / `viewer` / `enterprise` / `engineer` 只在 `SEED_DEMO_USERS=true` 时创建；
同一开关会幂等写入 10 条 FDE 演示订单（含工作日志）。**这些弱口令只用于本机开发。**

## 常用操作

```bash
# 查看日志
docker compose logs -f api
docker compose logs -f web

# 只重启后端（改了代码后重新构建）
docker compose up -d --build api

# 只起数据库，后端/前端在宿主机上跑（热更新更快）
docker compose up -d db

# 停止
docker compose down

# 连数据库一起清空（会删除所有用户与 token）
docker compose down -v && docker compose up --build -d
```

容器启动顺序：`db` 健康 → `api` 执行 `alembic upgrade head` + 种子脚本 → `api` 健康 → `web` 启动。后端镜像内部的 `scripts/entrypoint.sh` 负责迁移和种子，重复启动是幂等的。

## 宿主机本地开发

只起 `db`，后端和前端各自用原生工具链：

```bash
# 1. 数据库
docker compose up -d db

# 2. 后端
cd ../services/python-hub-api
cp .env.example .env          # DATABASE_URL 用 localhost:5432
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run fastapi dev            # http://127.0.0.1:8000

# 3. 前端（另一个终端）
cd ../clients/web
pnpm install
pnpm dev                      # Vite 默认 5173；被占用会自动换端口
```

Vite 把 `/api` 代理到 `http://127.0.0.1:8000`（含 WebSocket 升级），所以开发时不需要 CORS，
订单大厅的实时连接也能直接工作。

## 镜像源限制

如果本机无法直连 Docker Hub，可在 `.env` 里覆盖镜像地址，不需要改 `compose.yaml`：

```dotenv
POSTGRES_IMAGE=<mirror>/library/postgres:18
PYTHON_IMAGE=<mirror>/library/python:3.13-slim
NODE_IMAGE=<mirror>/library/node:24-alpine
NGINX_IMAGE=<mirror>/library/nginx:1.29-alpine
```

或者先 `docker pull` 代理镜像再 `docker tag` 成上面的标准名。`ghcr.io/astral-sh/uv` 用于后端构建阶段，需可访问。

## 数据与安全

- 数据库数据在命名卷 `pgdata`，`down` 不删除；`down -v` 才删除。
- `.env` 不提交。`JWT_SECRET` 在非 development 环境会拒绝示例值。
- 访问 token 默认 15 分钟、refresh token 默认 7 天；refresh 在 PG 里只存 SHA-256，刷新即旋转，旧 token 重放会吊销该用户全部会话。
- 本编排是本地演示用途：HTTP、弱口令、端口直接暴露，不要照搬到生产。
