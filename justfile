default:
    @just --list

compose := "docker compose -f deploy/compose.yaml --env-file deploy/.env"
python_image := env_var_or_default("PYTHON_IMAGE", "python:3.13-slim")

# 构建镜像并后台启动全部服务；可只启动某个服务及其依赖：just up api
up *args:
    {{ compose }} up -d --build {{ args }}

# 停止并删除容器（保留数据卷）
down:
    {{ compose }} down --remove-orphans

# 重启服务：just restart / just restart api
restart *args:
    {{ compose }} restart {{ args }}

# 查看日志：just logs -f api / just logs -f web
logs *args:
    {{ compose }} logs --tail=200 {{ args }}

# 查看容器与健康状态
ps:
    {{ compose }} ps

# 只构建镜像：just build / just build api
build *args:
    {{ compose }} build {{ args }}

# 生成随机十六进制密钥：just gen-secret 16（POSTGRES_PASSWORD）/ just gen-secret 32（JWT_SECRET）
gen-secret bytes="32":
    docker run --rm {{ python_image }} python -c "import secrets; print(secrets.token_hex({{ bytes }}))"
