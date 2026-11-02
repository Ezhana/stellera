# 允许通过 build arg 指向镜像代理（例如内网 registry），默认仍是官方镜像。
# infra/compose.yaml 的 api.build.args 会传 PYTHON_IMAGE；deploy/ 的测试环境编排
# 还会传 UV_IMAGE，方便 ghcr.io 不可直连的测试机。
#
# uv 镜像单独声明成命名 stage：BuildKit 不支持 `COPY --from=${ARG}` 的变量展开，
# 先 `FROM ${UV_IMAGE} AS uv` 再 `COPY --from=uv` 是官方 workaround。
# uv 固定到具体版本，避免 `latest` 漂移导致不同机器上锁文件校验行为不一致；
# 内网镜像代理请同样固定到对应 tag（见 deploy/env/staging.env.example）。
ARG PYTHON_IMAGE=python:3.13-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.6
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE}

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 非 root 运行；uid/gid 固定便于宿主机挂载时排查权限。
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home app

# 先复制依赖清单，充分利用 Docker 层缓存。
COPY pyproject.toml uv.lock ./
# --frozen：严格按 uv.lock 安装，不检查、不更新锁文件。
# 镜像构建环境（不同平台的 uv / 镜像代理索引）曾对 --locked 的锁校验行为不一致，
# 报 "The lockfile at uv.lock needs to be updated"；构建统一从锁文件安装保证可复现。
# 依赖变更请在服务目录执行 `uv lock` 并提交 uv.lock，再重新构建镜像。
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app . .
# 构建上下文可能来自 Windows / 共享盘等不保留 Unix 权限与换行的环境：
# 显式恢复入口脚本的可执行位并去掉 CRLF，否则容器启动会报
# exec: "/app/scripts/entrypoint.sh": permission denied / bad interpreter。
RUN sed -i 's/\r$//' /app/scripts/entrypoint.sh \
    && chmod 755 /app/scripts/entrypoint.sh
RUN uv sync --frozen --no-dev

USER app

EXPOSE 8000

# 与 compose healthcheck 一致：/health/ready 会检查 DB 与 Casbin。
HEALTHCHECK --interval=10s --timeout=5s --start-period=25s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
# 入口脚本的子命令分发：serve（默认，迁移 + seed + 启动 API）、migrate、seed、smoke；
# 其它参数透传执行。一次性任务复用同一镜像，例如
# `docker compose run --rm migrate` / `--rm seed` / `--rm smoke`。
# fastapi CLI 接受「文件/目录路径」而不是 import 字符串；不传路径时自动发现 app/main.py 里的 app。
CMD ["serve"]
