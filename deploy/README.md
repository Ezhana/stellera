# deploy/

面向**测试环境（staging）**的 Docker-only 发布编排：一台装了 Docker 的测试机，`git pull` 后
用脚本构建镜像、起容器、备份与回滚，不依赖 Kubernetes、Helm 或私有镜像仓库。

> 本地开发/演示用的全栈编排在 [`infra/`](../infra/README.md)，两者互不影响：
> `infra/` 面向本机、端口直连、可随意重建；`deploy/` 面向测试机，带版本 tag、发布前备份、
> 健康检查与回滚能力。

## 前置条件

- 测试机：Linux（或 macOS） + Docker + Docker Compose v2+（v2/v5 均可，`docker compose version` 可用）；
- 能访问仓库代码（`git clone` / `git pull`），以及 Docker Hub / ghcr.io；
  内网受限时在 env 里配镜像代理（见「镜像源限制」）；
- 端口：默认 8080 对外；8000 只绑 `127.0.0.1`（可改）。被占用时改 `WEB_PORT` / `API_PORT`；
- 磁盘：镜像与数据库卷需要数 GB 空间（API 镜像约 600MB）。

## 目录结构

```text
deploy/
├── docker-compose/
│   └── compose.yaml            # 测试环境编排：db + api + web
├── env/
│   └── staging.env.example     # 变量模板（真实 *.env 不提交）
├── scripts/
│   ├── lib/common.sh           # 公共函数（路径、env 校验、compose 封装、状态记录）
│   ├── init-env.sh             # 生成 env 并随机生成 JWT_SECRET / 数据库密码
│   ├── deploy.sh               # 一键发布（构建 → 备份 → 启动 → 健康 → 冒烟 → 记录）
│   ├── rollback.sh             # 回滚到上一版本（切镜像 tag，不重建）
│   ├── status.sh               # 容器/健康/版本/入口/备份概览
│   ├── logs.sh                 # 查看日志
│   ├── down.sh                 # 停止环境（默认保留数据卷）
│   ├── smoke-test.sh           # 冒烟测试（入口 / 登录 / RBAC / 订单 / WS）
│   ├── db-backup.sh            # pg_dump 备份
│   └── db-restore.sh           # 从备份恢复（危险操作，需确认）
└── README.md
```

## 首次部署

在测试机的仓库根目录：

```bash
git pull

# 1. 生成测试环境变量（自动生成 JWT_SECRET 与数据库密码，文件权限 600）
deploy/scripts/init-env.sh --env staging

# 2. 按需修改 deploy/env/staging.env：
#    - WEB_PORT（默认 8080）
#    - CORS_ORIGINS 加上测试机 IP 或域名，例如 http://192.168.1.10:8080
#    - 内网镜像代理（可选，见下文）
$EDITOR deploy/env/staging.env

# 3. 一键部署（首次会构建镜像，耗时几分钟）
deploy/scripts/deploy.sh --env staging
```

部署成功后：

| 地址 | 说明 |
| --- | --- |
| `http://<测试机>:8080/login` | 登录页（含「测试环境演示账号」，点击即填） |
| `http://<测试机>:8080/intro` | 平台简介 |
| `http://<测试机>:8080/fde/hall` | FDE 订单大厅（WebSocket 实时更新） |
| `http://127.0.0.1:8000/health/ready` | API + DB 就绪检查（仅本机） |

演示账号（`SEED_DEMO_USERS=true` 时由后端 seed 创建，密码为模板默认值）：

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `admin12345` | 管理员（全部权限） |
| `enterprise` | `enterprise12345` | 企业发布方 |
| `engineer` | `engineer12345` | 接单工程师 |
| `operator` | `operator12345` | 平台运营 |
| `viewer` | `viewer12345` | 只读 |

这些弱口令**仅限内网测试环境**：登录页会明文列出并支持一键填充（需求如此）。
生产环境必须 `SEED_DEMO_USERS=false` 并替换所有 `SEED_*_PASSWORD`、`POSTGRES_PASSWORD`、
`JWT_SECRET`——`deploy.sh` 会在 `APP_ENV=production` 时直接拒绝弱口令与演示账号。

## 日常发布

测试机上的标准流程：

```bash
git pull
deploy/scripts/deploy.sh --env staging
```

`deploy.sh` 依次做：

1. 校验 `deploy/env/<env>.env`（缺密钥/仍是占位值会直接失败）；
2. 计算发布版本：`git describe --tags --always --dirty`（工作区有未提交改动会提示）；
3. 如果数据库已在运行，先用 env 里的 `POSTGRES_PASSWORD` 做一次连接预检
   （密码与已有数据卷不一致时立刻失败，不会部署到一半才报错）；
4. `docker compose build` 构建镜像，tag 为 `<IMAGE_PREFIX>-hub-api:<版本>` 与 `-hub-web:<版本>`；
5. 发布前自动 `pg_dump` 备份到 `deploy/.state/backups/`（首次部署 / db 未运行时跳过）；
6. `docker compose up -d --remove-orphans`，等待 api healthcheck 与 web `/healthz`；
7. 跑 `smoke-test.sh`：首页 200、登录、带 token 拉订单、未认证 401、WebSocket 握手 101；
8. 成功后把版本写入 `deploy/.state/<env>/current`，旧版本写入 `previous`。

常用参数：

```bash
deploy/scripts/deploy.sh --env staging --version v0.2.0   # 指定版本 tag
deploy/scripts/deploy.sh --env staging --no-cache         # 依赖/基础镜像更新后重构
deploy/scripts/deploy.sh --env staging --no-build         # 仅重启，用现有镜像
deploy/scripts/deploy.sh --env staging --skip-backup      # 跳过发布前备份（不推荐）
deploy/scripts/deploy.sh --env staging --skip-smoke       # 跳过冒烟测试（不推荐）
```

> 版本 tag 规则：每次发布产生一个「版本 + 镜像」的对应关系，旧镜像**不要** `docker image prune`，
> 否则无法回滚。需要清理时只删明确不再使用的 tag。
>
> 同一环境不要并发执行 `deploy.sh` / `rollback.sh`（发布状态与备份目录没有加锁）；
> 同一台机器跑多个环境时，用不同的 `COMPOSE_PROJECT_NAME` 和端口，互不覆盖。

## 回滚

```bash
# 回滚到上一个发布版本（读取 deploy/.state/<env>/previous）
deploy/scripts/rollback.sh --env staging

# 回滚到指定版本
deploy/scripts/rollback.sh --env staging --to v0.1.0
```

回滚只切换应用镜像，**不会回滚数据库 schema**：

- 若发布包含 Alembic 迁移，旧代码可能与新 schema 不兼容；
- 需要时可恢复发布前备份：`deploy/scripts/db-restore.sh --env staging --file <备份文件>`；
- 回滚同样会先备份数据库，并跑一遍冒烟测试。

## 备份与恢复

```bash
# 手动备份（文件名：<env>-<时间戳>-<label>.sql.gz）
deploy/scripts/db-backup.sh --env staging --label manual

# 恢复（会先停 api；默认要求输入 restore 确认）
deploy/scripts/db-restore.sh --env staging --file deploy/.state/backups/staging-20260101-120000-manual.sql.gz
```

- 备份目录默认 `deploy/.state/backups`，可用 `BACKUP_DIR` 改；
- 自动清理超过 `BACKUP_KEEP_DAYS`（默认 14）天的备份；
- `deploy/.state/` 已被 `.gitignore` 忽略；重要环境建议再同步到异地。

## 状态、日志与停止

```bash
deploy/scripts/status.sh --env staging          # 容器、健康、当前/上一版本、入口、最近备份
deploy/scripts/logs.sh --env staging            # 全部服务，跟随
deploy/scripts/logs.sh --env staging api        # 只看 api
deploy/scripts/logs.sh --env staging --tail 500 --no-follow web

deploy/scripts/down.sh --env staging            # 停容器，保留数据库数据
deploy/scripts/down.sh --env staging --volumes  # 连数据卷一起删（需输入 delete-data 确认）
```

## 配置项

真实值放在 `deploy/env/<env>.env`（模板 `deploy/env/staging.env.example`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEPLOY_ENV` | `staging` | 环境名，也是状态目录名 |
| `COMPOSE_PROJECT_NAME` | `stellera-hub-staging` | Compose project 名；同机多环境必须不同 |
| `IMAGE_PREFIX` | `stellera` | 镜像名前缀 |
| `WEB_BIND` / `WEB_PORT` | `0.0.0.0` / `8080` | 对外入口（唯一对外端口） |
| `API_BIND` / `API_PORT` | `127.0.0.1` / `8000` | API 端口，默认仅本机可访问 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `hub` / 占位 / `hub` | 数据库；db 不映射宿主机端口 |
| `APP_ENV` | `staging` | 后端运行环境（非 development 会校验 JWT_SECRET） |
| `DEBUG` / `DOCS_ENABLED` | `false` / `false` | 调试与 Swagger 开关 |
| `JWT_SECRET` | 占位 | 至少 32 字符；`init-env.sh` 自动生成 |
| `ACCESS_TOKEN_TTL_SECONDS` / `REFRESH_TOKEN_TTL_SECONDS` | `900` / `604800` | 令牌有效期 |
| `CORS_ORIGINS` | 本机 8080 | 逗号分隔；同源部署其实不需要，但别配成 `*` |
| `SEED_*` | 弱口令 | 测试环境演示账号与 10 条演示订单开关 |
| `BACKUP_BEFORE_DEPLOY` | `true` | 发布/回滚前自动备份 |
| `BACKUP_DIR` / `BACKUP_KEEP_DAYS` | `.state/backups` / `14` | 备份位置与保留天数 |

### 镜像源限制

测试机不能直连 Docker Hub / ghcr.io 时，在 env 里把基础镜像换成内网代理即可，无需改
Dockerfile 或 compose：

```dotenv
POSTGRES_IMAGE=<mirror>/library/postgres:18
PYTHON_IMAGE=<mirror>/library/python:3.13-slim
UV_IMAGE=<mirror>/astral-sh/uv:0.13.6
NODE_IMAGE=<mirror>/library/node:24-alpine
NGINX_IMAGE=<mirror>/library/nginx:1.29-alpine
```

> `UV_IMAGE` 请固定到具体版本（默认是 `ghcr.io/astral-sh/uv:0.13.6`），不要用 `latest`：
> 不同 uv 版本的锁文件校验行为可能不同，会在构建时报
> `The lockfile at uv.lock needs to be updated`。镜像构建统一使用 `uv sync --frozen`，
> 以 `uv.lock` 为唯一来源；改依赖时在 `services/python-hub-api` 里执行 `uv lock` 并提交。

### 密码与 URL

`DATABASE_URL` 是 `postgresql+asyncpg://<用户>:<密码>@db:5432/<库>`，密码里含 `@ : / ? # %`
等字符会破坏 URL 解析。`init-env.sh` 生成的密码是十六进制串，天然安全；手工改密码时请只使用
`A-Z a-z 0-9 - _ .`，或自行做 URL 编码。

## 故障排查

| 现象 | 排查 |
| --- | --- |
| `deploy.sh` 报环境变量占位值 | 先跑 `init-env.sh`，或手工替换 `JWT_SECRET` / `POSTGRES_PASSWORD` |
| 对已有数据的环境 `init-env --force` 后 api 连不上库 | 数据库密码变了但数据卷里还是旧密码；同步改库密码，或 `down.sh --volumes` 重建（会丢数据） |
| 构建失败（拉基础镜像超时） | 配置内网镜像代理（见「镜像源限制」），或先 `docker pull` 后 `docker tag` 成标准名 |
| 构建报 `The lockfile at uv.lock needs to be updated` | 镜像构建已改用 `uv sync --frozen`；若仍出现，检查 `UV_IMAGE` 是否被覆盖成过旧/过新的 uv，固定到 `0.13.6` 与 Dockerfile 一致；依赖变更请 `uv lock` 后提交 |
| 容器启动报 `exec: "/app/scripts/entrypoint.sh": permission denied` | 构建上下文（Windows/共享盘）丢失了可执行位；Dockerfile 已 `sed + chmod` 兜底，重新构建即可（加 `--no-cache` 确保刷新该层） |
| 容器启动报 `bad interpreter` / 脚本里出现 `\r` | 构建上下文是 CRLF 换行；Dockerfile 已做 `sed` 兜底，仓库也加了 `.gitattributes` 强制 shell 脚本 LF |
| api 未就绪 | `deploy/scripts/logs.sh --env staging api`；常见原因是数据库密码与 `POSTGRES_PASSWORD` 不一致 |
| 8080 被占用 | 改 env 的 `WEB_PORT` 后重新 `deploy.sh --env staging` |
| 页面 502 / WebSocket 断开 | 先看 `logs.sh api`；nginx 需要能解析 compose 服务名 `api`，确认 web 与 api 同 project |
| 回滚提示镜像不存在 | 旧镜像已被 `docker image prune` 清理；用 `deploy.sh --version <旧版本>` 重建，或恢复备份 |
| 登录失败 | 确认 `SEED_DEMO_USERS=true` 且数据库初始化成功（`logs.sh api` 找 seed 日志） |

## 安全边界

- 只对外开放 web 的 `${WEB_PORT}`；db 不映射宿主机端口，api 默认只绑 `127.0.0.1`；
- 测试环境按需求保留弱口令演示账号，登录页明文展示——**仅限内网测试**；
- `deploy/env/*.env` 与 `deploy/.state/` 不提交；真实密钥只在测试机上；
- 目前是纯 Docker 单机编排；需要高可用/多副本时再引入 K8s/Helm 或托管数据库，
  注意后端实时推送是单进程内存实现（`app.state.realtime_hub`），多副本需要额外广播方案。
