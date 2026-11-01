# 0001 — 登录与 RBAC：Authlib JWT + pycasbin 自建守卫 + PG 角色模型

- 状态：已采纳
- 日期：2026-11-01

## 背景

Stellera Hub 是基于 RBAC 的 Console 端，后续会有钱包、订单、广场等模块。登录模块需要：

- 用户名/密码登录，签发可校验的访问令牌；
- 按 URL + HTTP 方法做权限控制，权限可随模块扩展；
- 用户、角色、权限持久化在 PostgreSQL；
- 本地用 Docker 一条命令起全栈。

后端基于 FastAPI 模板。最初的方案是引入 `Authlib + fastapi-casbin-auth`，但 `fastapi-casbin-auth==1.5.0` 在元数据里硬锁 `fastapi==0.121.2`、`starlette==0.49.3`，与模板要求的 FastAPI `>=0.141.1` 冲突；强行安装只能把框架整体降级约一年。

## 决策

1. **放弃 `fastapi-casbin-auth`，直接用 `pycasbin` 写守卫。**
   - 该包的全部逻辑约 60 行：依赖 Starlette `AuthenticationMiddleware` 设置 `scope["user"]`，再调用 `enforcer.enforce(subject, path, method)`。
   - 自建 `CasbinRBACMiddleware` 保留同样的 `(subject, path, method)` 模型，但补充：路径归一化（防尾斜杠/重复斜杠绕过）、未认证 401 / 已认证但无权限 403 的区分、`OPTIONS` 放行。
   - FastAPI/Starlette 可以继续用当前最新版，不需要 `[tool.uv] override-dependencies`。

2. **Authlib 负责 JWT。**
   - 使用 `authlib.jose.jwt` 签发和校验 access/refresh token，HS256，校验 `exp`、`iss`、`aud`、`sub`、`typ`。
   - Authlib 1.9 已将 `authlib.jose` 标记为 deprecated（1.x 内保持兼容，建议迁移 `joserfc`）。当前 pin `authlib>=1.9,<2`，并把 JWT 逻辑集中在 `app/core/security.py` 的 `TokenService`，为后续迁移留出单一改动点。

3. **密码哈希用 `pwdlib[argon2]`。**
   - Argon2id，不自己实现 salt/hash。登录失败对不存在的用户也执行一次 dummy verify，降低用户名枚举的时序差异。

4. **RBAC 数据以 PostgreSQL 为源，启动时投影到 Casbin。**
   - 表：`users`、`roles(parent_id)`、`permissions(object, action)`、`role_permissions`、`user_roles`。
   - `casbin/model.conf` 只放模型（`keyMatch2` + `regexMatch`），不存 policy CSV。
   - 启动时把角色权限投影为 `p, role:<name>, <object>, <regex>`，角色继承投影为 `g, role:<child>, role:<parent>`，用户角色投影为 `g, user:<id>, role:<role>`；所有登录用户额外加入 `role:authenticated`，保证至少能访问 `/auth/me` 与 `/auth/logout`。
   - 主体加 `user:` / `role:` 前缀，避免用户名恰好等于角色名时被 Casbin 当成同一个主体。
   - 角色变更在下一次登录或重启后生效；多 worker 部署下需要重启/重载。v0.1 接受，后续可接 Casbin SQLAlchemy adapter 或管理 API。

5. **刷新令牌入库并旋转。**
   - refresh token 只存 SHA-256；刷新时校验 `jti` + hash，吊销旧行并签发新对。
   - 旧 refresh token 被重放时，吊销该用户全部 refresh token，前端收到 401 后清空会话。

6. **本地全栈用 `infra/compose.yaml`。**
   - PostgreSQL 18 + API + nginx 托管的前端；API 容器启动时自动迁移和 seed。
   - `deploy/` 仍负责发布环境，`infra/` 只做本地开发/演示。

## 代价

- 自建守卫需要自己维护测试（已有中间件单测覆盖 401/403、公开路径、路径归一化），换来的是不锁旧框架、行为可控。
- 角色/权限修改不会热更新到已运行的进程；需要重新登录或重启。对当前“登录模块”范围足够。
- 前端 token 存在 localStorage/sessionStorage，XSS 可读；当前 BFF 是前端内的适配/页面模型层（见 ADR 0002），不是服务端 BFF。要真正隐藏 token，需要后续引入服务端 BFF + httpOnly cookie。

## 被否掉的方案

| 方案 | 否决原因 |
| --- | --- |
| 固定 FastAPI 0.121.2 / Starlette 0.49.3 使用 `fastapi-casbin-auth` | 新项目整体降级约一年，且 Pydantic 也被锁版本 |
| uv override 绕过 `fastapi-casbin-auth` 的硬锁 | 组合不受包支持，`pip install` 不生效，长期维护风险高 |
| 用 Authlib 的 OAuth2 server 做完整 password grant | Starlette 没有官方 server 集成，首版收益低；当前需求是 JWT + RBAC |
| 只把角色放 JWT、不做 Casbin | 权限变更要等 token 过期，且无法按 URL/方法细粒度控制 |

## 后续

- 第三方 OAuth2/OIDC 登录（Authlib Starlette client）作为独立模块接入。
- RBAC 管理 API/UI（角色、权限、用户分配）可直接基于现有表结构实现。
- 视需要把进程内 Casbin 投影替换为数据库 adapter，并支持热重载。
