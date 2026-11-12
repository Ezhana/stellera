# 应用数据库密码 secret

`infra/postgres/compose.yaml` 的 `postgres-provision` 一次性 job 通过 compose secret
读取本目录的密码文件，为各应用创建/同步独立数据库与账号：

| secret 文件 | 应用 | 数据库 / 账号 |
| --- | --- | --- |
| `litellm_db_password` | LiteLLM 网关 | `litellm` / `litellm` |
| `new_api_db_password` | new-api 网关 | `new-api` / `new-api` |
| `grafana_db_password` | Grafana | `grafana` / `grafana` |
| `hub_db_password` | hub-api | `hub` / `hub` |

真实密码文件已被 [.gitignore](.gitignore) 忽略，仓库只提交 `*.example` 模板。

## 首次使用

```bash
# 从模板生成真实 secret 文件
cd infra/postgres/secrets
for f in *.example; do cp "$f" "${f%.example}"; done
```

生成后请把各文件内容换成随机密码（`openssl rand -hex 16`），并同步到使用方：

- `litellm_db_password` → `infra/litellm/.env` 的 `DATABASE_URL` 密码；
- `new_api_db_password` → `infra/new-api/.env` 的 `SQL_DSN` 密码；
- `hub_db_password` → `deploy/.env`（或 `services/hub-api/.env`）的 `HUB_DATABASE_URL` / `DATABASE_URL` 密码；
- `grafana_db_password` → Grafana 通过 compose secret 直接读取，无需重复填写。

> 注意：secret 文件是数据库密码的唯一来源；provision job 会把角色密码同步成文件内容，
> 使用方连接串里的密码必须与之保持一致。
