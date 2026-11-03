# 构建上下文是 pnpm workspace 根（clients/web），APP 为 apps/<APP> 的目录名兼包名：
#   docker build -f clients/web/Dockerfile --build-arg APP=hub clients/web
ARG NODE_IMAGE=node:24-alpine
ARG NGINX_IMAGE=nginx:1.29-alpine

FROM ${NODE_IMAGE} AS base
ARG NPM_REGISTRY=
ARG COREPACK_NPM_REGISTRY=
ENV npm_config_registry=${NPM_REGISTRY} \
    pnpm_config_registry=${NPM_REGISTRY}
WORKDIR /workspace
RUN set -eu; \
    registry="${COREPACK_NPM_REGISTRY:-${NPM_REGISTRY}}"; \
    if [ -n "${registry}" ]; then export COREPACK_NPM_REGISTRY="${registry}"; fi; \
    corepack enable && corepack prepare pnpm@12.4.2 --activate

FROM base AS pruner
ARG APP
RUN test -n "${APP}" || (echo "缺少 build-arg APP（apps/<APP> 的目录名兼包名）" >&2; exit 1)
COPY . .
RUN TURBO_VERSION="$(node -p 'require("./package.json").devDependencies.turbo')" \
    && pnpm dlx "turbo@${TURBO_VERSION}" prune "${APP}" --docker

FROM base AS build
ARG APP
COPY --from=pruner /workspace/out/json/ ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY --from=pruner /workspace/out/full/ ./
RUN pnpm exec turbo run build --filter="${APP}"

FROM ${NGINX_IMAGE} AS runtime
ARG APP
COPY --from=build /workspace/apps/${APP}/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/${APP}/dist /usr/share/nginx/html
RUN chmod a+r /etc/nginx/conf.d/default.conf \
    && chmod -R a+rX /usr/share/nginx/html
EXPOSE 80
