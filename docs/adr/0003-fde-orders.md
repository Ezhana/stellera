# 0003 — FDE 订单模块：订单状态机、第三方托管与 WebSocket 实时大厅

- 状态：已采纳
- 日期：2026-11-02

## 背景

产品从“钱包 / 订单 / 广场”的通用 Console 转向 FDE（Forward Deployed Engineer，前沿部署工程师）交付平台。核心业务闭环是：

```text
企业发布需求 -> 平台代收并托管资金 -> 工程师接单交付（提交工作日志）-> 平台验收结算
```

首期需要交付两件事：

1. 左侧菜单支持二级结构；保留平台简介（轮播图 + 叙事），删除钱包 / 广场等旧模块；
2. FDE 订单模块的第一个页面——**实时订单大厅**，展示任务、行业、交付周期、价格、状态；同时提供“我发布的”入口。

这要求后端新增订单域、资金托管状态、工程师工作日志与实时推送；前端新增一套订单 BFF、页面模型与 WebSocket 客户端。

## 决策

### 1. 独立 `/api/v1/fde` 模块与订单状态机

- 新增 `fde_orders`、`fde_order_logs` 两张表，订单字段直接覆盖大厅展示需求（标题、行业、交付天数、价格、状态、发布方/工程师、日志数、时间戳）。
- 价格以 **整数分** 存储（`price_cents`），避免浮点金额误差；上限 10 亿分（1000 万元）。
- 状态机保持最小闭环：
  - `open --claim--> in_progress --complete--> completed`
  - `open --cancel--> cancelled`
- 工作日志只在 `in_progress` 状态由接单工程师提交；日志数用于大厅与详情展示，不引入额外的事件表。
- 单号 `FDE-<year>-<序号>` 对用户可读，演示数据使用 `FDE-DEMO-xxxx` 前缀，种子幂等。

### 2. 第三方托管用订单字段表达，不引入真实支付账本

- 订单增加 `escrow_status`：`held`（平台代收/托管）、`released`（验收后放款）、`refunded`（取消退回）。
- 状态流转由服务层在同一事务内完成：发布 → `held`，完成 → `released`，取消 → `refunded`。
- v0.1 只表达托管状态，不对接支付渠道、不做分账与对账；未来接入支付账本时，把 `escrow_status` 的写操作替换为调用账本服务即可，订单状态机不变。

### 3. RBAC：在 authenticated 之上增加 enterprise / engineer 两个角色

- 角色树由单链扩展为：

  ```text
  authenticated
  ├── viewer -> operator -> admin
  ├── enterprise（发布 / 完成 / 取消）
  └── engineer（认领 / 提交日志）
  ```

- 读权限挂在 `authenticated`（所有登录用户都能看订单大厅）；写权限按动作收窄到具体路径，admin 仍由 `/api/v1/*` 全量通配覆盖。
- 演示账号：`enterprise / enterprise12345`、`engineer / engineer12345`，与原有 admin/operator/viewer 一起由 seed 幂等创建。

### 4. 实时推送用进程内 WebSocket Hub

- 端点：`WebSocket /api/v1/fde/ws?token=<access_token>`。浏览器 WebSocket 不能设置 `Authorization` 头，所以令牌放 query，由端点用既有 `TokenService` 校验；Casbin 中间件只覆盖 HTTP scope，因此 WS 鉴权在端点内完成。
- 连接建立后先发 `connected` 帧；订单创建/认领/日志/完成/取消后广播 `order.created` / `order.updated`（携带完整订单 JSON）。
- Hub 是 `app.state` 上的单进程内存集合，发送失败的连接自动移除，lifespan 退出时统一关闭。
- 前端使用指数退避重连（1s→2s→4s→8s→15s），令牌失效的 4401 关闭码不重连；连接状态以 `connecting / live / reconnecting / offline` 暴露给页面。
- 单进程 Hub 的取舍：v0.1 单 worker 部署足够；多 worker 时每个进程只推自己的连接，前端刷新列表兜底。需要跨进程广播时再换成 Redis pub/sub 或 Postgres LISTEN/NOTIFY。

### 5. 前端沿用 ADR 0002 的 BFF 分层

- 新增 `src/bff/orders/`：`dto.ts`（zod，唯一出现 snake_case 的地方）、`mapper.ts`（DTO → `FdeOrderView`，价格/日期/状态/托管文案）、`gateway.ts`（HTTP 端口）、`realtime.ts`（WS 端口）、`service.ts`（`OrdersBff` 编排）。
- 页面只消费 `FdeOrderView` 与 `OrderListModel`；实时事件也先经过 mapper 再进入页面。
- 页面需要 token 时通过 `authBff.accessToken()` 这个 BFF-to-BFF 的窄端口获取，token 仍然不进入页面/store。
- 列表在客户端过滤与排序（大厅一次取最多 100 条），实时事件用 `upsertOrder` 合并；统计（待接单、交付中、托管金额）由前端从订单列表推导，避免额外的后端聚合接口。
- 页面模型不暴露后端字段名；新增后端枚举时 mapper 有降级路径，不会打挂大厅。

### 6. 二级导航由前端持有

- 新增 `models/nav.ts` 描述 `平台 -> 平台简介`、`FDE 订单 -> 订单大厅 / 我发布的` 两级树；`ConsoleLayout` 从当前路由名解析激活项并自动展开所在分组。
- 删除旧的钱包/广场模块目录与“控制台总览”页，`/console` 保留为跳转 `/intro` 的兼容入口；登录后默认落到平台简介。
- 平台简介页用纯 CSS 轮播（渐变 + 网格 + 金色焦点）承载叙事，不引入图片资源或轮播依赖；支持键盘、hover/focus 暂停、`prefers-reduced-motion` 关闭自动播放。

## 代价

- 实时依赖单进程内存 Hub；水平扩容前需要引入广播中间件。
- 令牌放在 WS query 中，可能出现在代理访问日志里；生产环境应使用短期一次性 ticket 或 httpOnly cookie（需要服务端 BFF）。
- 托管只是状态字段，没有真实资金账本；“平台收取企业资金”在 v0.1 是产品语义而非支付实现。
- 大厅暂以“取前 100 条 + 客户端过滤”实现，订单量上来后需要分页/虚拟列表。
- 认领、日志、完成目前只有 API 与数据模型，页面交互（接单、日志时间线、验收）放在后续迭代。

## 被否掉的方案

| 方案 | 否决原因 |
| --- | --- |
| 用轮询（每 3–5 秒拉列表）实现“实时” | 首屏抖动、无事件语义，服务端压力与订单量线性增长 |
| SSE 推送 | EventSource 同样无法自定义 Authorization 头，且现有 nginx/Vite 代理需要额外配置；WS 双向能力更适合后续接单/日志同步 |
| 把订单状态塞进通用 `orders` 表 | 老模块没有业务闭环；FDE 需要托管、日志、工程师等专属字段，独立模块更清晰 |
| 金额用浮点/字符串 | 浮点有精度风险；分存整数是支付域惯例 |
| 前端直接连 WS 并在页面里解析后端字段 | 违反 ADR 0002 的 BFF 边界，后端字段变化会穿透页面 |
| 用现成轮播库 | 只有 3 张幻灯片，纯 CSS + 少量状态即可；少一个运行时依赖 |

## 后续

- 支付账本/托管账户与对账；企业充值、退款、平台服务费。
- 工程师端：接单、日志时间线、交付物上传、里程碑。
- 企业端：需求编辑、验收与争议流程。
- 订单详情页与大厅分页/筛选下沉到服务端。
- 多 worker 实时广播与 Redis/Postgres 适配。
- 订单域 ADR 细化：交付验收状态、SLA 与超时规则。
