# STELLERA HUB 前端镜像。
#
# 构建上下文是 pnpm workspace 根目录 clients/web（不是 apps/hub），因此请在仓库根目录执行：
#   docker build -f clients/web/apps/hub/Dockerfile clients/web
#
# 构建阶段只安装 hub 需要的依赖并执行 vite build；运行阶段用 nginx 托管静态产物，
# 并通过 nginx.conf 提供 SPA history 回退与 /api 反向代理。
ARG NODE_IMAGE=node:24-alpine
ARG NGINX_IMAGE=nginx:1.29-alpine
FROM ${NODE_IMAGE} AS build

WORKDIR /workspace

# 固定与 package.json 中 packageManager 一致的 pnpm 版本。
RUN corepack enable && corepack prepare pnpm@12.4.2 --activate

# 先复制 workspace 清单，最大化利用 Docker 层缓存。
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/hub/package.json ./apps/hub/package.json

RUN pnpm install --frozen-lockfile --ignore-scripts

# 再复制应用源码并构建。
COPY apps/hub ./apps/hub

RUN pnpm --filter hub build

FROM ${NGINX_IMAGE} AS runtime

COPY apps/hub/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/hub/dist /usr/share/nginx/html

# nginx worker 以非 root 运行；确保静态资源与配置对 worker 可读，
# 避免宿主文件权限（600）被 COPY 进镜像后导致 403。
RUN chmod a+r /etc/nginx/conf.d/default.conf \
    && chmod -R a+rX /usr/share/nginx/html

EXPOSE 80
