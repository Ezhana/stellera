# 允许通过 build arg 指向镜像代理（例如内网 registry），默认仍是官方镜像。
# infra/compose.yaml 的 api.build.args 会传 PYTHON_IMAGE；deploy/ 的测试环境编排
# 还会传 UV_IMAGE，方便 ghcr.io 不可直连的测试机。
#
# uv 镜像单独声明成命名 stage：BuildKit 不支持 `COPY --from=${ARG}` 的变量展开，
# 先 `FROM ${UV_IMAGE} AS uv` 再 `COPY --from=uv` 是官方 workaround。
ARG PYTHON_IMAGE=python:3.13-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest
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
RUN uv sync --locked --no-dev --no-install-project

COPY --chown=app:app . .
RUN uv sync --locked --no-dev

USER app

EXPOSE 8000

# 与 compose healthcheck 一致：/health/ready 会检查 DB 与 Casbin。
HEALTHCHECK --interval=10s --timeout=5s --start-period=25s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
# fastapi CLI 接受「文件/目录路径」而不是 import 字符串；不传路径时自动发现 app/main.py 里的 app。
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
