# 0004 钱包模块与管理员后台

## 背景

控制台在 FDE 订单模块之后需要恢复“钱包”入口，并补齐超级管理员的管理菜单。需求边界：

- 钱包展示余额、用量（消费流水）、充值和兑换码；
- 在线充值暂不开放，只保留入口、档位与历史记录；
- 超级管理员可见“用户 / 兑换码 / 系统设置”管理菜单，普通用户不可见也不可访问；
- FDE 订单与钱包打通：发布需求从余额扣款托管，取消退回，确认交付结算给接单工程师。

此前 `rbac.toml` 中曾有“wallet 已下线”的注释，本次重新上线需要同步清理并补回权限。

## 决策

### 账本模型

- `wallets`：每个用户一行，`balance_cents` 以分为单位存整数，避免浮点误差；
- `wallet_transactions`：只追加的流水，记录 `type`（recharge / redeem / order_payment /
  order_refund / order_settlement）、`direction`（credit / debit）、金额和 `balance_after_cents`；
- 余额只通过服务层的 `credit` / `debit` 变更，不允许端点直接改 `balance_cents`；
- 汇总口径：用量 = 所有 debit 合计，充值 / 兑换 / 结算收入按 type 分别累计。

### FDE 资金流

```text
发布需求  wallet debit  ->  escrow held
取消订单  wallet credit <-  escrow refunded（退回发布方）
确认交付  wallet credit <-  escrow released（结算给接单工程师）
```

订单状态机不变，仍是 `open -> in_progress -> completed / cancelled`；钱包变动与订单状态写入
同一个数据库事务，避免“扣了钱没建单”或“完成订单没结算”。余额扣减使用 `SELECT ... FOR UPDATE`
锁钱包行，SQLite 测试会自动忽略该子句。

### 兑换码

- 管理员按批次生成，格式 `RDM-XXXX-XXXX-XXXX`，字段含面额、批次号、可空过期时间、备注；
- 一次性使用：兑换时先做状态/过期校验，再用条件 UPDATE（`status='active'` 且未过期）占用，
  `rowcount == 1` 才算成功，避免并发重复入账；
- 管理员可停用/重新启用未使用的码，已使用的码不可回退；过期码不可启用。

### 在线充值

`recharge_enabled` 恒为 `false`，设计上不接支付渠道：钱包页展示金额档位但按钮置灰，文案与
客服联系方式从系统设置读取；只保留充值流水（演示数据中是线下充值）。等真正接入支付后，
再增加下单/回调端点并打开开关。

### 系统设置

不引入任意 KV 配置，只维护三键白名单：`platform_name`、`support_contact`、
`wallet_recharge_note`。只插入缺失默认值，重跑种子不覆盖管理员已修改的内容。

### 管理后台与权限

- 管理端路由统一挂在 `/api/v1/admin/*`，Casbin 只放行 `admin` 角色，端点内再用
  `load_user_role_names` 做一次角色校验（双保险，防止策略误配）；
- 停用用户时吊销其全部 refresh token，access token 最长 15 分钟后自然失效；
- 修改角色后立即 `resync_user`，无需等下一次登录；
- 保护性约束：不能停用自己、不能移除自己的 admin、不能移除最后一个 admin；
- 前端导航由 `navForViewer` 过滤 `requiresAdmin` 分组，路由守卫对非 admin 重定向回平台简介。

## 代价与后续

- 发布订单现在依赖余额：生产环境首次部署没有充值渠道时，只能通过管理员生成兑换码给用户充值；
- 管理员能力限定为“列表/搜索/启停/改角色”，暂不提供创建用户、重置密码、删除账号；
- 流水表当前没有对账/冲正流程，`order_settlement` 只记录结算入账；若后续要支持退款争议，
  需要新增反向交易类型而不是修改历史行；
- 钱包页的“充值档位”是展示性质的常量，后续接支付时再改为服务端返回。
