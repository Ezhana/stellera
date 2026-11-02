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
│   ├── models/                 # users / roles / permissions / refresh_tokens / fde_orders / fde_order_logs
│   ├── schemas/                # 请求/响应模型（auth.py、fde.py）
│   ├── security/               # TokenService（Authlib JWT）+ 密码哈希
│   ├── rbac/                   # Casbin 模型投影、公开策略
│   ├── realtime/hub.py         # FDE 订单 WebSocket 连接中心（app.state.realtime_hub）
│   ├── middleware/             # JWTAuthBackend + CasbinRBACMiddleware
│   ├── services/               # auth.py（登录/刷新/me）、fde.py（订单状态机与托管资金）
│   ├── api/v1/endpoints/       # auth.py、fde.py（含 WebSocket）、health.py
│   └── scripts/seed.py         # 幂等种子数据（角色/权限/演示账号/FDE 演示订单）
├── casbin/model.conf           # 只放模型，policy 不落 CSV
├── migrations/                 # Alembic（异步 env.py + 0001 初始迁移 + 0002 FDE 订单）
├── scripts/entrypoint.sh       # 容器入口：serve/migrate/seed/smoke 子命令
├── tests/                      # SQLite + TestClient，不依赖 Docker/PG
├── alembic.ini
└── Dockerfile                  # python:3.13-slim + uv + 非 root
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
`SEED_DEMO_USERS=true` 时额外创建 `operator / operator12345`、`viewer / viewer12345`、
`enterprise / enterprise12345`（企业（演示））与 `engineer / engineer12345`（工程师（演示）），
并写入 10 条 FDE 演示订单（`FDE-DEMO-0001` … `FDE-DEMO-0010`）。

## 配置

所有配置经 `app/core/config.py` 的 `Settings` 读取，变量名与
`infra/compose.yaml`、`.env.example` 一致；配置在启动时由 Pydantic Settings 校验，
不合规直接 fail-fast（例如非 development 环境仍使用示例 `JWT_SECRET`）。

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
| `SEED_DEMO_USERS` | `true` | 是否创建 operator/viewer/enterprise/engineer 演示账号与 FDE 演示订单 |
| `SEED_OPERATOR_PASSWORD` / `SEED_VIEWER_PASSWORD` | `operator12345` / `viewer12345` | 运营/访客演示账号密码 |
| `SEED_ENTERPRISE_PASSWORD` / `SEED_ENGINEER_PASSWORD` | `enterprise12345` / `engineer12345` | 企业/工程师演示账号密码 |

## API

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 公开 | JSON `{username, password}`，返回令牌 + `user` |
| POST | `/api/v1/auth/token` | 公开 | OAuth2 password form（Swagger Authorize），返回纯令牌 |
| POST | `/api/v1/auth/refresh` | 公开（凭 refresh token） | 旋转 refresh token |
| POST | `/api/v1/auth/logout` | Bearer | 吊销该用户全部 refresh token，204 |
| GET | `/api/v1/auth/me` | Bearer | 当前用户、角色、Casbin 隐式权限 |
| GET | `/api/v1/fde/orders` | Bearer | FDE 订单大厅，支持 `status` / `industry` / `q` / `page` / `page_size` |
| GET | `/api/v1/fde/orders/mine` | Bearer | 我发布的 FDE 订单，可选 `status` |
| GET | `/api/v1/fde/orders/{order_id}` | Bearer | FDE 订单详情（含 `logs`，最旧在前） |
| POST | `/api/v1/fde/orders` | Bearer（enterprise/admin） | 发布需求，201，返回订单 |
| POST | `/api/v1/fde/orders/{order_id}/claim` | Bearer（engineer/admin） | 工程师认领订单 |
| POST | `/api/v1/fde/orders/{order_id}/logs` | Bearer（接单工程师/admin） | 提交工作日志，201 |
| POST | `/api/v1/fde/orders/{order_id}/complete` | Bearer（publisher/admin） | 确认交付，托管资金 `released` |
| POST | `/api/v1/fde/orders/{order_id}/cancel` | Bearer（publisher/admin） | 取消待认领订单，托管资金 `refunded` |
| WS | `/api/v1/fde/ws?token=<access_token>` | Bearer（query token） | FDE 订单实时推送 |
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

## FDE 订单模块

企业发布需求（平台代收并托管资金）→ 工程师认领 → 工程师提交工作日志 → 企业确认交付并释放托管资金。

订单状态机与资金托管：

```text
open --claim--> in_progress --complete--> completed
  └── cancel --> cancelled
escrow: held --complete--> released / --cancel--> refunded
```

- 订单 JSON 字段：`id/code/title/industry/description/delivery_days/price_cents/status/
  escrow_status/publisher/engineer/work_log_count/created_at/updated_at/claimed_at/completed_at`；
  `publisher` / `engineer` 为 `{id, display_name}`（`display_name` 取 `full_name`，为空时回退 `username`）；
- 列表响应统一信封 `{items, total, page, page_size}`，按 `created_at desc, id desc` 排序；
  `status` 只接受 `open/in_progress/completed/cancelled`，`page_size` 范围 1..100；
- 单号格式 `FDE-<年份>-<4 位序号>`；演示订单固定为 `FDE-DEMO-0001` … `FDE-DEMO-0010`，
  由 `SEED_DEMO_USERS=true` 时幂等写入（5 条 open、3 条 in_progress、2 条 completed，含 11 条工作日志）；
- 业务错误：订单不存在 → 404；状态机不允许（已认领 / 状态不符 / 认领自己发布的订单）→ 409；
  已认证但非发布者 / 非接单工程师 → 403；
- 时间统一以 UTC 序列化为 RFC 3339（例如 `2026-11-01T06:20:00Z`）；
- 实时推送：`WS /api/v1/fde/ws?token=<access_token>`（浏览器 WebSocket 无法带 Authorization 头，
  令牌从 query 读取并由 `TokenService` 校验）。连接后先收 `{"type":"connected","server_time":"..."}`；
  每次成功变更（create/claim/log/complete/cancel）向所有在线连接广播
  `{"type":"order.created"|"order.updated","order":{...}}`，`order` 与 HTTP 反序列化结构完全一致
  （claim / log / complete / cancel 都是 `order.updated`，带最新 `work_log_count`）；
  令牌缺失或无效时以关闭码 `4401` 断开（服务端先完成握手再关闭，浏览器才能拿到
  自定义关闭码；握手阶段直接拒绝只会得到 1006）；
- 连接中心是单进程内存实现（挂在 `app.state.realtime_hub`），lifespan 关闭时统一断开。

```json
{
  "type": "order.updated",
  "order": {
    "id": 1,
    "code": "FDE-2026-0001",
    "title": "医疗影像 AI 辅助诊断 PoC",
    "industry": "医疗健康",
    "description": "…",
    "delivery_days": 21,
    "price_cents": 8600000,
    "status": "in_progress",
    "escrow_status": "held",
    "publisher": { "id": 4, "display_name": "企业（演示）" },
    "engineer": { "id": 5, "display_name": "工程师（演示）" },
    "work_log_count": 1,
    "created_at": "2026-11-01T06:20:00Z",
    "updated_at": "2026-11-01T07:10:00Z",
    "claimed_at": "2026-11-01T07:00:00Z",
    "completed_at": null
  }
}
```

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
authenticated            所有登录用户的基线（/auth/me GET、/auth/logout POST、fde/orders* GET）
├── viewer               只继承 authenticated 的只读能力（wallet/plaza/旧 orders 已下线）
│   └── operator         同上（旧模块的运营写权限已随模块删除）
│       └── admin        /api/v1/* 全方法（含 /api/v1/admin/* 与 FDE 全部操作）
├── enterprise           fde/orders POST、fde/orders/*/complete、fde/orders/*/cancel
└── engineer             fde/orders/*/claim、fde/orders/*/logs
```

权限按模块路径收窄，viewer / operator 只能读取当前上线模块；需要新增模块时，
在 `app/scripts/seed.py` 的 `PERMISSION_DEFINITIONS` 里补对应路径即可。

中间件顺序（外 → 内）：`CORS` → `AuthenticationMiddleware` → `CasbinRBACMiddleware`。
启动时从数据库加载 RBAC；`app.state.enforcer` / `app.state.session_factory` 供依赖注入使用。

## 数据库与迁移

```bash
uv run alembic upgrade head        # 应用迁移
uv run alembic downgrade -1        # 回滚一步
uv run alembic revision -m "msg"   # 新建迁移
```

模型在 `app/models/`，初始迁移为 `migrations/versions/0001_initial_schema.py`，
FDE 订单表在 `migrations/versions/0002_fde_orders.py`（`fde_orders` + `fde_order_logs`，
FK 指向 `users`，单号唯一，`status` / `publisher_id` / `created_at` 建索引）。
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
401 与 403 区分、角色继承矩阵、路径归一化、OPTIONS 放行、健康检查、种子幂等，
以及 FDE 订单全流程（大厅过滤/分页、发布、认领、工作日志、完成/取消、我发布的、
管理员跨角色操作、WebSocket 鉴权与 `order.created` / `order.updated` 推送）。

也可以从仓库根目录用 `just`（薄转发，等价）：

```bash
just backend-lint
just backend-test
just backend-typecheck
just backend-build      # uv build，产物在 dist/
just backend-serve
```

根目录没有 `package.json` 与 lockfile，不需要 `npm install`；`just` 只把命令转发到本目录，实际工具链仍是 uv。

## Docker

```bash
docker build -t stellera-hub-api .
docker run --rm -p 8000:8000 --env-file .env stellera-hub-api
```

镜像基于 `python:3.13-slim`，用 uv 安装依赖，非 root（uid 10001）运行。
`scripts/entrypoint.sh` 支持 `serve`（默认：先 `alembic upgrade head`、再幂等 seed，最后
exec `fastapi run --host 0.0.0.0 --port 8000`，CLI 自动发现 `app/main.py` 里的 app）、
`migrate`（只跑迁移）、`seed`（只写种子）与 `smoke`（冒烟检查）子命令，其余参数透传执行；
一次性任务复用同一镜像，例如 `docker compose run --rm migrate` / `--rm seed` / `--rm smoke`。

如果 Docker Hub 不可直连，可通过 build arg 指定镜像代理（默认仍是官方 tag）：

```bash
docker build --build-arg PYTHON_IMAGE=registry.example.com/python:3.13-slim .
```

本地全栈（PostgreSQL + API + nginx 前端）见 `infra/compose.yaml`；该文件会把
`PYTHON_IMAGE` 作为 build arg 传进来。

## 与仓库其他部分的关系

- 前端在 `clients/web`，通过 `/api/v1/auth/*`、`/api/v1/fde/*`（含 `/api/v1/fde/ws` 实时推送）
  与 `/health/ready` 对接；
- `infra/` 负责本地 Docker 编排，`deploy/` 负责发布环境；
- CI 直接在本服务目录跑原生命令：`uv run ruff check .`、`uv run ruff format --check .`、
  `uv run ty check app tests`、`uv run pytest` 和 `uv build`，不依赖根目录工具链。
