# Stellera monorepo 统一入口：本地开发与发布都从这里触发。
#
# 设计约定：
#   - 不依赖 Nx。每个项目自带工具链（前端 pnpm、后端 uv），just 只调用它们；
#   - just 只做薄壳转发：没有循环、日期、chmod、find、awk 和条件校验。
#     构建在 Dockerfile / CI，就绪在 compose healthcheck + depends_on，
#     配置校验在后端 Pydantic Settings（不合规直接 fail-fast），
#     备份 / 恢复 / 冒烟 / 迁移是一次性任务，逻辑在镜像内，用
#     `docker compose run --rm <job>` 触发；
#   - 发布版本取当前 git 提交（git describe），作为不可变镜像 tag；
#     回滚时用 `just RELEASE_VERSION=<历史 tag> rollback <env>` 覆盖；
#   - 发布类 recipe 的环境用参数传，默认 staging，读取 deploy/env/<env>.env。
#
# 不带参数运行 `just` 会列出全部 recipe。

# 发布版本（不可变镜像 tag）：当前 git 提交，工作区有改动时带 -dirty。
export RELEASE_VERSION := shell("git describe --tags --always --dirty")

# 部署编排命令前缀（只做转发，不在这里写任何部署逻辑）。
compose := "docker compose -f deploy/docker-compose/compose.yaml"

# 生成随机密钥用的 Python 镜像；内网可 export PYTHON_IMAGE=<镜像代理地址> 覆盖。
python_image := env_var_or_default("PYTHON_IMAGE", "python:3.13-slim")

# 不传参数时列出所有可用 recipe（默认行为）
default:
    @just --list

# ---------- 本地开发：后端（uv，服务自带 pyproject.toml / uv.lock） ----------

# 后端本地依赖就绪：起本地 db → uv sync → Alembic 迁移 → 种子数据
backend-setup:
    docker compose -f infra/compose.yaml up -d db
    uv sync --directory services/python-hub-api
    uv run --directory services/python-hub-api alembic upgrade head
    uv run --directory services/python-hub-api python -m app.scripts.seed

# 后端开发服务器（热更新，http://127.0.0.1:8000，Swagger 在 /docs）
[working-directory('services/python-hub-api')]
backend-serve:
    uv run fastapi dev --host 0.0.0.0 --port 8000

# 后端 lint：ruff check + format check
[working-directory('services/python-hub-api')]
backend-lint:
    uv run ruff check .
    uv run ruff format --check .

# 后端自动格式化与修复
[working-directory('services/python-hub-api')]
backend-fmt:
    uv run ruff check --fix .
    uv run ruff format .

# 后端类型检查（ty）
[working-directory('services/python-hub-api')]
backend-typecheck:
    uv run ty check app tests

# 后端测试（pytest，SQLite，不依赖 Docker）
[working-directory('services/python-hub-api')]
backend-test:
    uv run pytest

# 后端构建（uv build，产物在服务内 dist/）
[working-directory('services/python-hub-api')]
backend-build:
    uv build

# ---------- 本地开发：前端（pnpm workspace，clients/web 自带锁文件） ----------

# 安装前端依赖
[working-directory('clients/web')]
frontend-install:
    pnpm install

# 前端开发服务器（Vite 默认 5173，/api 代理到 8000）
[working-directory('clients/web')]
frontend-dev:
    pnpm dev

# 前端构建（产物在 clients/web/apps/hub/dist）
[working-directory('clients/web')]
frontend-build:
    pnpm build

# 前端 lint（根 ESLint + 各 app）
[working-directory('clients/web')]
frontend-lint:
    pnpm lint

# 前端类型检查（vue-tsc）
[working-directory('clients/web')]
frontend-typecheck:
    pnpm -r --filter "./apps/*" --if-present run type-check

# ---------- 本地开发：前后端一起跑 ----------

# 前后端并行开发（Ctrl-C 一起退出；shebang 脚本需 POSIX shell：macOS/Linux/WSL/Git Bash）
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT INT TERM
    uv run --directory services/python-hub-api fastapi dev --host 0.0.0.0 --port 8000 &
    pnpm --dir clients/web dev &
    wait

# ---------- 发布：staging/prod 单机 Docker Compose ----------
# 全部只是 `docker compose ...` 的转发；镜像、healthcheck、一次性 job、备份策略
# 分别在 services/python-hub-api/Dockerfile、deploy/docker-compose/compose.yaml、
# deploy/ops/ 里，宿主不承载业务逻辑。

# 发布：构建带版本 tag 的镜像 → 发布前备份 → up -d → 冒烟测试
deploy env="staging":
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops build
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm backup
    {{ compose }} --env-file deploy/env/{{ env }}.env up -d
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm smoke

# 回滚到指定版本（不构建，直接用历史镜像 tag）：just RELEASE_VERSION=<tag> rollback staging
rollback env="staging":
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm backup
    {{ compose }} --env-file deploy/env/{{ env }}.env up -d
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm smoke

# 启动/重启现有容器（如 down 之后；版本默认取当前 checkout）
up env="staging":
    {{ compose }} --env-file deploy/env/{{ env }}.env up -d

# 停止并删除容器（保留数据卷）；要连数据卷一起删：just down staging -v
down env="staging" extra="":
    {{ compose }} --env-file deploy/env/{{ env }}.env down --remove-orphans {{ extra }}

# 查看日志：just logs staging -f api / just logs staging --tail=500 web
logs env="staging" *args:
    {{ compose }} --env-file deploy/env/{{ env }}.env logs --tail=200 {{ args }}

# 查看容器/健康/镜像 tag 概览（发布状态从实际运行的镜像 tag 推导）
status env="staging":
    {{ compose }} --env-file deploy/env/{{ env }}.env ps

# 数据库备份（镜像内 pg_dump + 命名 + 保留天数）：just backup staging [label]
backup env="staging" label="manual":
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm -e BACKUP_LABEL={{ label }} backup

# 从备份恢复（危险操作；会先停 api，恢复后重新拉起）：
# just restore staging <备份文件名> [restore]   # 第三个参数传 restore 表示非交互确认
restore env="staging" file="" confirm="":
    {{ compose }} --env-file deploy/env/{{ env }}.env stop api
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm -e RESTORE_FILE=/backups/{{ file }} -e RESTORE_CONFIRM={{ confirm }} restore
    {{ compose }} --env-file deploy/env/{{ env }}.env start api

# 冒烟测试（入口 → nginx → api → DB → RBAC → WebSocket，全部在容器内跑）
smoke env="staging":
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm smoke

# 执行 Alembic 迁移（一次性 job）
migrate env="staging":
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm migrate

# 写入/刷新种子数据（一次性 job）
seed env="staging":
    {{ compose }} --env-file deploy/env/{{ env }}.env --profile ops run --rm seed

# ---------- 首次部署辅助 ----------

# 生成随机十六进制密钥（在一次性容器内生成，不依赖宿主 openssl）：
# JWT_SECRET 用 `just gen-secret 32`；POSTGRES_PASSWORD 用 `just gen-secret 16`
gen-secret bytes="32":
    docker run --rm {{ python_image }} python -c "import secrets; print(secrets.token_hex({{ bytes }}))"
