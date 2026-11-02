# ops 工具镜像：只承载数据库备份 / 恢复脚本，复用 postgres:18 自带的同版本
# pg_dump / psql（与 db 服务版本一致，避免 pg_dump 版本不匹配导致恢复失败）。
#
# 独立 tag：<IMAGE_PREFIX>-hub-ops:<OPS_IMAGE_TAG>，不随发布版本走；
# 回滚到历史版本时，备份 / 恢复能力仍然可用。
#
# 构建（由 just 的发布流程带 --profile ops 触发）：
#   docker compose -f deploy/docker-compose/compose.yaml \
#     --env-file deploy/env/staging.env --profile ops build backup restore
#
# 内网镜像代理：构建参数 POSTGRES_IMAGE 由 compose 从 env 传入。
ARG POSTGRES_IMAGE=postgres:18
FROM ${POSTGRES_IMAGE}

# 构建上下文可能来自 Windows / 共享盘，不保留可执行位与 LF 换行：
# 显式去掉 CRLF 并恢复可执行位（仓库 .gitattributes 已强制 *.sh eol=lf）。
COPY backup.sh restore.sh /opt/ops/
RUN sed -i 's/\r$//' /opt/ops/backup.sh /opt/ops/restore.sh \
    && chmod 755 /opt/ops/backup.sh /opt/ops/restore.sh

WORKDIR /opt/ops

# 不设置 ENTRYPOINT / CMD：由 compose 的 backup / restore 服务显式指定
# entrypoint（/opt/ops/backup.sh 与 /opt/ops/restore.sh）。
