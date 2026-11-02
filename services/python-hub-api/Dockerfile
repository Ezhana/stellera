# 允许通过 build arg 指向镜像代理 / 内网源，默认仍是官方镜像与官方 PyPI。
# infra/compose.yaml 与 deploy/ 的测试环境编排都会传 PYTHON_IMAGE / UV_IMAGE / PIP_*；
# 单镜像手构建示例见 services/python-hub-api/README.md「Docker」。
#
# uv 镜像单独声明成命名 stage：BuildKit 不支持 `COPY --from=${ARG}` 的变量展开，
# 先 `FROM ${UV_IMAGE} AS uv` 再 `COPY --from=uv` 是官方 workaround。
# uv 默认跟随 `latest` 的最新版本；需要完全可复现的构建时，可在 env 里覆盖成具体版本。
ARG PYTHON_IMAGE=python:3.13-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE}

COPY --from=uv /uv /uvx /bin/

# ---------- pip 源（构建期安装依赖） ----------
# 通过 build arg 配置 pip 源，留空则使用官方 PyPI。
# uv 不读取 pip 的 PIP_* 环境变量，这里显式映射成 uv 自己的索引配置：
#   PIP_INDEX_URL       -> UV_DEFAULT_INDEX（主索引）
#   PIP_EXTRA_INDEX_URL -> UV_EXTRA_INDEX_URL（附加索引）
#   PIP_TRUSTED_HOST    -> UV_INSECURE_HOST（http 源放行主机，填 host 或 host:port，不带 scheme）
# 变量为空时 uv 按未设置处理，保持默认官方源。
ARG PIP_INDEX_URL=
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=
ENV UV_DEFAULT_INDEX=${PIP_INDEX_URL} \
    UV_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL} \
    UV_INSECURE_HOST=${PIP_TRUSTED_HOST}

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
