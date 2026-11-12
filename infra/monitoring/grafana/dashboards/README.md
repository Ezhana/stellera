# LiteLLM dashboards

把 LiteLLM 官方 Grafana dashboard 的 JSON 放到本目录，Grafana 启动时会通过
`../provisioning/dashboards/dashboards.yml` 自动加载。

- 全量指标 dashboard：
  <https://github.com/BerriAI/litellm/tree/main/cookbook/litellm_proxy_server/grafana_dashboard/dashboard_all_metrics>
- 精简 v2 dashboard：
  <https://github.com/BerriAI/litellm/tree/main/cookbook/litellm_proxy_server/grafana_dashboard/dashboard_v2>

当前为预留目录，默认没有预置 dashboard。
