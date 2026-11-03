# Stellera

多语言 monorepo：根目录只做编排——唯一入口是 [`just`](https://github.com/casey/just)，项目各自带工具链
（前端 pnpm workspace、后端 uv）。根目录没有 `package.json` / lockfile，也没有根级任务调度器或根级依赖安装：

| 项目 | 目录 | 工具链 | 说明 |
| --- | --- | --- | --- |
| `hub`（web） | `clients/web` | pnpm workspace（Node 24） | Vue 3 + Vite 前端工作区，应用在 `apps/hub`（Obsidian 黑金 FDE 交付控制台：平台简介 + 实时订单大厅 + 钱包 + 个人信息/认证 + 管理后台，含 BFF/页面模型层） |
| `hub-api` | `services/hub-api` | uv（Python 3.13） | FastAPI + PostgreSQL，Authlib JWT 登录、pycasbin RBAC、FDE 订单/实时推送、个人资料/认证、钱包与管理后台 |

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
`member / enterprise / engineer` 演示账号、10 条 FDE 演示订单、钱包余额/流水、3 个演示兑换码，
以及 5 条演示认证申请（企业/工程师各含实名与企业/工程师认证，会员有一条待审核实名）。

| 地址 | 说明 |
| --- | --- |
| <http://localhost:8080/login> | 登录页（中文黑金商务风 / Obsidian） |
| <http://localhost:8080/register> | 注册页（用户名 + 邮箱，注册即会员、昵称自动生成） |
| <http://localhost:8080/intro> | 平台简介（轮播图 + 叙事；登录后的默认页） |
| <http://localhost:8080/fde/hall> | FDE 订单大厅（WebSocket 实时更新） |
| <http://localhost:8080/fde/published> | 我发布的（发布需求、取消、确认交付） |
| <http://localhost:8080/fde/assigned> | 我接到的（提交日志、申请交付） |
| <http://localhost:8080/fde/applications> | 我的申请（我发起的 / 待我审批） |
| <http://localhost:8080/fde/orders/:id> | 订单详情（订单信息、双方资料、日志、全部申请审批记录） |
| <http://localhost:8080/profile> | 个人信息（资料编辑、认证申请、合作记录） |
| <http://localhost:8080/profiles/:id> | 他人公开主页（登录后可看） |
| <http://localhost:8080/wallet> | 钱包（余额、用量、充值记录、兑换码） |
| <http://localhost:8080/admin/users> | 管理后台（仅 admin：用户 / 认证审核 / 兑换码 / 系统设置） |
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

业务闭环：**发布需求 → 平台代收并托管资金 → 接单方申请接单 → 发布方通过 → 提交日志 → 申请交付 → 发布方验收 → 平台结算**。

- 左侧菜单为两级：`平台 → 平台简介`、`FDE 订单 → 订单大厅（实时）/ 我发布的 / 我接到的 / 我的申请`、
  `钱包 → 我的钱包`、`个人 → 个人信息`；超级管理员额外看到 `管理 → 用户 / 认证审核 / 兑换码 / 系统设置`。
- 角色体系：注册即成为 `member`；`realname`（实名）、`enterprise` / `engineer` 是认证身份
  （认证即授予角色，仅作展示，可叠加为实名 + 企业或实名 + 工程师）；所有登录用户都可以发布订单、
  申请接单、提交日志、申请交付；`admin` 额外拥有管理端权限。
- 接单与交付都走**申请 + 发布者审批**：申请接单通过后订单进入进行中，申请交付通过后订单完成并结算；
  同订单其它待审批申请自动驳回；接单方不能单方面取消已接订单，发布者可取消待接单订单并退款。
- 订单有独立详情页：订单信息、托管状态、发布方/接单工程师资料卡、工作日志、该订单全部申请与
  审批人/时间/理由（即历史审批记录），并按当前用户与状态提供操作。
- 实时更新走 `WebSocket /api/v1/fde/ws`：创建、申请审批引发的状态变化、日志、取消都会广播
  `order.created` / `order.updated`，断线自动重连，刷新列表兜底。
- 认证标识：实名/企业/工程师认证在侧边栏、订单发布者/接单工程师、申请列表、公开主页展示；
  用户提交认证申请，管理员在「认证审核」页通过/驳回。
- API 一览见 [`services/hub-api/README.md`](services/hub-api/README.md)，
  取舍记录见 [`docs/adr/0003-fde-orders.md`](docs/adr/0003-fde-orders.md) 与
  [`docs/adr/0005-roles-order-applications.md`](docs/adr/0005-roles-order-applications.md)。

## 个人信息与认证

- 注册只填用户名 + 邮箱（唯一）+ 密码，昵称由系统自动生成，可在个人信息里修改；
- 个人信息页支持修改昵称、邮箱、介绍、技能标签、城市、联系电话/微信，并展示认证与合作记录；
- 合作记录按**已完成订单**统计（我发布的 + 我接到的）：完成单数、合作方数、累计金额，最近 20 条明细；
- 他人公开主页（登录后可看）展示昵称、介绍、技能、城市、认证和合作记录，隐藏实名、邮箱与联系方式；
- 三类认证：
  - 实名认证：真实姓名、身份证号、手机号，管理员审核后写入实名；
  - 企业认证：公司名、统一社会信用代码、联系人/电话、资质说明；
  - 工程师认证：技能、工作年限、项目经历、联系电话；
  企业/工程师申请前必须已完成实名；企业与工程师互斥（新认证替换旧认证），实名可与之叠加；
- 认证审核页：管理员按状态/类型/关键字筛选，查看完整申请资料，通过或驳回（可填理由）；
  通过后自动授予对应角色并刷新权限，驳回后可重新提交。
- 详细取舍见 [`docs/adr/0006-profile-certification.md`](docs/adr/0006-profile-certification.md)。

## 钱包与管理后台

钱包页展示**可用余额、累计用量、充值与兑换码**四个区域。余额以“分”存储，每次变更都写入
`wallet_transactions` 流水（充值 / 兑换 / 订单消费 / 退款 / 结算），页面同时展示流水明细与累计口径。

- **在线充值暂不开放**：充值页保留金额档位与历史充值记录，按钮置灰，说明与客服联系方式来自系统设置；
- **兑换码**：管理员按批次生成 `RDM-XXXX-XXXX-XXXX` 一次性兑换码，用户在钱包页输入即可入账；
- **FDE 资金打通**：发布需求时从发布方余额扣款托管，取消订单退回，确认交付后结算给接单工程师，
  变动与订单状态在同一事务内完成；
- **管理后台（仅超级管理员 `admin`）**：
  - 用户：搜索、按角色筛选、启用/停用；编辑昵称/邮箱、通过增减流水调整余额（认证统一走认证审核页）；
  - 认证审核：实名/企业/工程师认证申请列表、通过/驳回（可填理由）；
  - 兑换码：按状态/关键词筛选、批量生成、停用/启用；
  - 系统设置：平台名称、客服联系方式、充值说明（白名单键值，不覆盖已有修改）；
- 非管理员前端不渲染“管理”菜单，直接访问 `/admin/*` 路由会被重定向回平台简介。

接口与权限细节见 [`services/hub-api/README.md`](services/hub-api/README.md) 与
[`docs/adr/0004-wallet-admin.md`](docs/adr/0004-wallet-admin.md)。

## 本地开发（热更新）

环境要求：Python 3.13（见 `services/hub-api/.python-version`）、uv、Node.js 24（见 `clients/web/package.json`
的 `engines`；pnpm 由 corepack 按 `packageManager` 字段自动取用）、Docker（只用于本地依赖）。

依赖初始化（首次，在仓库根目录）：

```bash
cp infra/.env.example infra/.env
docker compose -f infra/compose.yaml up -d    # PostgreSQL（new-api、hub 库）+ Redis + new-api

cd services/hub-api
cp .env.example .env          # DATABASE_URL 改成 infra/.env 里的用户/密码（默认 stellera / stellera）
uv sync
uv run python -m app.scripts.init --demo
```

前端依赖（首次）：

```bash
cd clients/web
pnpm install
```

之后用 `just` 启动本地开发服务器（热更新）：

```bash
just api    # 后端 http://127.0.0.1:8000，Swagger 在 /docs
just web    # 前端 http://localhost:5173，/api 代理到 8000
just dev    # 前后端并行，Ctrl-C 一起退出
```

## just 命令

`just` 是仓库唯一编排入口：只做薄壳转发——本地开发转发 uv / pnpm，部署转发 `deploy/compose.yaml`。
不带参数运行 `just` 会列出全部 recipe。

```bash
# 本地开发（uv / pnpm）
just api                    # 后端热更新，127.0.0.1:8000
just web                    # 前端 Vite，localhost:5173
just dev                    # 前后端并行

# Docker 部署（deploy/compose.yaml）
just up [service...]        # 构建镜像并后台启动（不带参数=全部；如 just up api）
just down                   # 停止并删除容器（保留数据卷）
just restart [service...]   # 重启服务
just logs [args...]         # 日志：just logs -f api / just logs -f web
just ps                     # 容器 / 健康状态
just build [service...]     # 只构建镜像
just gen-secret [bytes]     # 生成随机十六进制密钥（默认 32 字节）
```

`just` 只做薄壳转发：本地开发直接调用 uv / pnpm，部署直接转发 compose（例如 `just ps` 等价于
`docker compose -f deploy/compose.yaml --env-file deploy/.env ps`）。

## 目录

```text
justfile                      # 根编排入口（薄壳转发，无业务逻辑）
clients/web/                  # 前端工作区：apps/hub、共享 ESLint/Prettier 配置、通用 Dockerfile
services/hub-api/             # 后端服务：app/、casbin/、migrations/、tests/
infra/                        # 本地依赖编排：postgres/、redis、new-api/
deploy/                       # 发布编排：compose.yaml（include infra + hub-api/web）与 .env.example
docs/adr/                     # 架构决策记录（0001 登录与 RBAC、0002 前端 BFF/页面模型、0003 FDE 订单、0004 钱包与管理后台、0005 角色与订单申请、0006 个人信息与认证）
tools/                        # 仓库级维护工具（gen-api 等，按需创建）
```

## CI

GitHub Actions 在 push / PR 时并行跑两个 job：后端 `services/hub-api` 用
`uv run ruff check` / `ruff format --check` / `uv run ty check app tests` / `uv run pytest` / `uv build`，
前端 `clients/web` 用 `pnpm lint` / `pnpm -r --if-present run test` / `pnpm build` / vue-tsc 类型检查。
没有根级安装步骤，也没有 affected 增量调度，见 [.github/workflows/ci.yml](.github/workflows/ci.yml)。

各子项目的补充说明见其目录下的 README（如 `services/hub-api`、`clients/web`）。
