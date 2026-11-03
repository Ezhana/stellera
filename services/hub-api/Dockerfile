ARG PYTHON_IMAGE=python:3.13-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE}

COPY --from=uv /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 内网构建时传入 uv 索引；留空使用官方 PyPI。
ARG UV_DEFAULT_INDEX=
ARG UV_EXTRA_INDEX_URL=
ARG UV_INSECURE_HOST=

COPY pyproject.toml uv.lock ./
# 镜像源与 uv.lock 记录的来源不一致时 --locked 必然失败；先按镜像源重写锁文件（仅镜像内）。
RUN export UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX}" \
        UV_EXTRA_INDEX_URL="${UV_EXTRA_INDEX_URL}" \
        UV_INSECURE_HOST="${UV_INSECURE_HOST}"; \
    [ -z "${UV_DEFAULT_INDEX}${UV_EXTRA_INDEX_URL}" ] || uv lock; \
    uv sync --locked --no-dev --no-install-project

COPY . .
RUN export UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX}" \
        UV_EXTRA_INDEX_URL="${UV_EXTRA_INDEX_URL}" \
        UV_INSECURE_HOST="${UV_INSECURE_HOST}"; \
    [ -z "${UV_DEFAULT_INDEX}${UV_EXTRA_INDEX_URL}" ] || uv lock; \
    uv sync --locked --no-dev

# EXPOSE 只是默认值；实际监听端口由 PORT 覆盖。
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=25s --retries=10 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health/ready', timeout=3)"

CMD ["sh", "-c", "exec fastapi run --host 0.0.0.0 --port \"${PORT:-8000}\" --workers \"${WEB_CONCURRENCY:-1}\""]
