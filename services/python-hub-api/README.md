# Stellera Hub API（python-hub-api）

Stellera Hub 的后端服务：**FastAPI + PostgreSQL + Authlib JWT + pycasbin RBAC**。

对应架构决策见 [`docs/adr/0001-auth-rbac.md`](../../docs/adr/0001-auth-rbac.md)：
不使用 `fastapi-casbin-auth`（它会硬锁旧版 FastAPI/Starlette），而是用 `pycasbin`
自建约 60 行的守卫，换取框架版本自由与 401/403 行为可控。

## 技术栈

| 能力 | 选型 |
| --- | --- |
| Web | FastAPI `>=0.141.1`（Starlette 1.x、Pydantic 2.x） |
| 数据库 | SQLAlchemy 2.0 async + asyncpg + Alembic |
| JWT | Authlib `>=1.9,<2`（HS256，access + refresh） |
| 密码 | `pwdlib[argon2]`（Argon2id） |
| RBAC | `pycasbin` + PostgreSQL 投影（keyMatch2 + regexMatch） |
| 配置 | pydantic-settings |
| 工具 | uv / Ruff / ty / pytest / pre-commit / hatchling |

## 目录结构

```text
services/python-hub-api/
├── app/
│   ├── main.py                 # create_app 工厂 + lifespan（建引擎、投影 Casbin）
│   ├── db.py                   # async engine / session factory
│   ├── core/config.py          # Settings（环境变量唯一入口）
│   ├── models/                 # users / roles / permissions / user_roles / role_permissions / refresh_tokens
│   ├── schemas/                # 请求/响应模型
│   ├── security/               # TokenService（Authlib JWT）+ 密码哈希
│   ├── rbac/                   # Casbin 模型投影、公开策略
│   ├── middleware/             # JWTAuthBackend + CasbinRBACMiddleware
│   ├── services/auth.py        # 登录 / 刷新旋转 / 登出 / me
│   ├── api/v1/endpoints/       # auth.py、health.py
│   └── scripts/seed.py         # 幂等种子数据（python -m app.scripts.seed）
├── casbin/model.conf           # 只放模型，policy 不落 CSV
├── migrations/                 # Alembic（异步 env.py + 0001 初始迁移）
├── scripts/entrypoint.sh       # 容器入口：migrate -> seed -> exec
├── tests/                      # SQLite + TestClient，不依赖 Docker/PG
├── alembic.ini
├── Dockerfile                  # python:3.13-slim + uv + 非 root
└── project.json                # Nx targets: lint/test/typecheck/build/serve
```

## 快速开始（本地）

前置：Python 3.13（见 `.python-version`）、[uv](https://docs.astral.sh/uv/)。

```bash
cd services/python-hub-api
cp .env.example .env          # 按需修改 DATABASE_URL / JWT_SECRET
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run fastapi dev            # 自动发现 app/main.py，http://127.0.0.1:8000
```

只起数据库再本地跑后端（需要 Docker）：

```bash
docker compose -f ../../infra/compose.yaml up -d db
```

- Swagger：<http://127.0.0.1:8000/docs>
- 就绪探针：<http://127.0.0.1:8000/health/ready>

默认账号（来自 `.env.example`，仅供本机开发）：`admin / admin12345`；
`SEED_DEMO_USERS=true` 时额外创建 `operator / operator12345`、`viewer / viewer12345`。

## 配置

所有配置经 `app/core/config.py` 的 `Settings` 读取，变量名与
`infra/compose.yaml`、`.env.example` 一致。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | `development/test/staging/production` |
| `DEBUG` | `false` | 调试开关（SQL echo 用 `DATABASE_ECHO`） |
| `DOCS_ENABLED` | `true` | 关闭后 `/docs`、`/redoc`、`/openapi.json` 不再挂载 |
| `DATABASE_URL` | `postgresql+asyncpg://hub:hub_dev_password@localhost:5432/hub` | async SQLAlchemy URL；测试用 `sqlite+aiosqlite:///...` |
| `DATABASE_ECHO` | `false` | 打印 SQL |
| `JWT_SECRET` | 示例值 | **至少 32 字符**；非 development 环境拒绝示例值 |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `stellera-hub` / `stellera-hub-web` | JWT iss/aud 校验 |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | access token 有效期 |
| `REFRESH_TOKEN_TTL_SECONDS` | `604800` | refresh token 有效期 |
| `CORS_ORIGINS` | 本机 5173/8080 | 逗号分隔 |
| `CASBIN_MODEL_PATH` | `casbin/model.conf` | Casbin 模型文件 |
| `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` / `SEED_ADMIN_EMAIL` | `admin` / `admin12345` / `admin@example.com` | 管理员 |
| `SEED_DEMO_USERS` | `true` | 是否创建 operator/viewer 演示账号 |
| `SEED_OPERATOR_PASSWORD` / `SEED_VIEWER_PASSWORD` | `operator12345` / `viewer12345` | 演示账号密码 |

## API

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 公开 | JSON `{username, password}`，返回令牌 + `user` |
| POST | `/api/v1/auth/token` | 公开 | OAuth2 password form（Swagger Authorize），返回纯令牌 |
| POST | `/api/v1/auth/refresh` | 公开（凭 refresh token） | 旋转 refresh token |
| POST | `/api/v1/auth/logout` | Bearer | 吊销该用户全部 refresh token，204 |
| GET | `/api/v1/auth/me` | Bearer | 当前用户、角色、Casbin 隐式权限 |
| GET | `/health` | 公开 | 存活探针 |
| GET | `/health/ready` | 公开 | DB + Casbin 就绪探针 |

`/login` 响应示例（`/token`、`/refresh` 只返回令牌字段，不含 `user`）：

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_expires_in": 604800,
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "系统管理员",
    "is_active": true,
    "roles": ["admin"],
    "permissions": [
      { "object": "/api/v1/*", "action": "^(GET|POST|PUT|PATCH|DELETE)$" },
      { "object": "/api/v1/auth/me", "action": "^GET$" }
    ]
  }
}
```

`permissions` 来自 Casbin 的 `get_implicit_permissions_for_user`（含角色继承），
按 `(object, action)` 去重排序，供前端权限卡片展示。令牌类响应统一带
`Cache-Control: no-store`。

### 令牌与刷新旋转

- access token：HS256，claims 含 `iss/aud/sub/iat/nbf/exp/jti/typ=access`；
- refresh token：同结构、`typ=refresh`，数据库只存 `jti` 与令牌的 SHA-256；
- 刷新时校验 `jti + hash + exp`，吊销旧行并签发新对（rotation）；
- 旧 refresh token 被重放时，**吊销该用户全部 refresh token**，前端收到 401 后清空会话；
- logout 同样吊销全部 refresh token（access token 到期自然失效）。

## RBAC（Casbin）

`casbin/model.conf` 只放模型：`g(r.sub, p.sub) && keyMatch2(r.obj, p.obj) && regexMatch(r.act, p.act)`。

- policy 来自 PostgreSQL，启动时投影到进程内 enforcer：
  - `p, role:<name>, <object>, <action>`（来自 `role_permissions`）；
  - `g, role:<child>, role:<parent>`（来自 `roles.parent_id`）；
  - `g, user:<id>, role:<name>`（来自 `user_roles`）+ 所有用户自动加入 `role:authenticated`；
- 主体带 `user:` / `role:` 前缀，匿名主体为 `anonymous`，避免重名串角色；
- 登录时重新投影该用户的角色（角色变更下次登录生效，多 worker 需重启，v0.1 接受）；
- 公开策略（login/token/refresh/health/docs）写在 `app/rbac/policies.py`；
- 中间件行为：
  - 未认证 → 401（带 `WWW-Authenticate: Bearer`）；
  - 已认证但无权限 → 403；
  - `OPTIONS` 放行（交 CORS 处理）；
  - 路径归一化（`//`、尾斜杠）后再判断，防绕过。

角色树与种子权限：

```text
authenticated            所有登录用户的基线（/auth/me GET、/auth/logout POST）
└── viewer               wallet/* GET、orders GET、orders/* GET、plaza/* GET
    └── operator         orders POST/PATCH、orders/* PATCH/PUT、plaza/* POST/PUT/PATCH
        └── admin        /api/v1/* 全方法（含未来的 /api/v1/admin/*）
```

权限按模块路径收窄，viewer 的只读权限不会意外放开 `/api/v1/admin/*`；需要新增模块时，
在 `app/scripts/seed.py` 的 `PERMISSION_DEFINITIONS` 里补对应路径即可。

中间件顺序（外 → 内）：`CORS` → `AuthenticationMiddleware` → `CasbinRBACMiddleware`。
启动时从数据库加载 RBAC；`app.state.enforcer` / `app.state.session_factory` 供依赖注入使用。

## 数据库与迁移

```bash
uv run alembic upgrade head        # 应用迁移
uv run alembic downgrade -1        # 回滚一步
uv run alembic revision -m "msg"   # 新建迁移
```

模型在 `app/models/`，初始迁移为 `migrations/versions/0001_initial_schema.py`。
生产数据库是 PostgreSQL；测试用临时 SQLite（`sqlite+aiosqlite`），不依赖 Docker/PG。

## 质量检查

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run ty check app tests
uv run pytest
```

测试覆盖：密码哈希、JWT 签发/过期/篡改/类型混用、登录/刷新旋转/重放吊销/登出、
401 与 403 区分、角色继承矩阵、路径归一化、OPTIONS 放行、健康检查、种子幂等。

也可以走 Nx（从仓库根目录）：

```bash
npx nx run python-hub-api:lint
npx nx run python-hub-api:test
npx nx run python-hub-api:typecheck
npx nx run python-hub-api:build      # uv build，产物在 dist/
npx nx run python-hub-api:serve
```

## Docker

```bash
docker build -t stellera-hub-api .
docker run --rm -p 8000:8000 --env-file .env stellera-hub-api
```

镜像基于 `python:3.13-slim`，用 uv 安装依赖，非 root（uid 10001）运行；
`scripts/entrypoint.sh` 会先 `alembic upgrade head`、再幂等 seed，最后 exec 启动命令
（`fastapi run --host 0.0.0.0 --port 8000`，CLI 会自动发现 `app/main.py` 里的 app）。

如果 Docker Hub 不可直连，可通过 build arg 指定镜像代理（默认仍是官方 tag）：

```bash
docker build --build-arg PYTHON_IMAGE=registry.example.com/python:3.13-slim .
```

本地全栈（PostgreSQL + API + nginx 前端）见 `infra/compose.yaml`；该文件会把
`PYTHON_IMAGE` 作为 build arg 传进来。

## 与仓库其他部分的关系

- 前端在 `clients/web`，通过 `/api/v1/auth/*` 与 `/health/ready` 对接；
- `infra/` 负责本地 Docker 编排，`deploy/` 负责发布环境；
- 本服务是 Nx 项目 `python-hub-api`，根 CI 用 `nx affected` 跑 lint/test/build/typecheck。
