# 0005 角色体系与订单申请审批

## 背景

首版 RBAC 的角色树是 `authenticated → viewer → operator → admin`，再加 `enterprise` / `engineer`
两个 FDE 业务角色，订单接单与完成都是“直接认领 / 直接完成”。实际使用后需要调整：

- 注册即成为会员，不再由管理员逐一手工开号；
- 运营、访客两个角色没有独立业务含义，移除；
- 企业与工程师是认证身份，不是操作权限：所有登录用户都能发布和接受 FDE 订单；
- 接单与交付需要“申请 + 审批”，避免直接占用和单方面完成；
- 发布方需要“我发布的”，接单方需要“我接到的”，双方都需要“我的申请”；
- 管理员需要编辑用户资料、认证状态，并通过流水调整余额，而不是直接改余额字段。

## 决策

### 角色

```text
authenticated              登录基线
└── member                 注册即会员
    ├── enterprise          企业认证（认证即授予）
    ├── engineer            工程师认证（认证即授予）
    └── admin               超级管理员（/api/v1/* 全方法）
```

- `viewer` / `operator` 被移除；残留用户由种子迁移为 `member`；
- 旧演示账号 `operator` / `viewer` 在 demo 模式下删除（有订单引用时保留并转 member）；
- 注册接口 `POST /api/v1/auth/register` 公开，创建用户并授予 `member`，立即签发令牌；
- enterprise / engineer 角色不再附带任何操作权限，仅作为认证标识；FDE 与钱包权限统一下沉到
  `authenticated`，业务边界改由服务层按“发布者 / 接单工程师 / 申请人”判断。

### 认证

- 认证完全由角色派生：有 `enterprise` → 企业认证；否则有 `engineer` → 工程师认证；否则未认证；
- 管理员在用户编辑里选择“未认证 / 企业认证 / 工程师认证”，后端替换认证角色并确保 `member` 基线；
- 订单、日志、申请中的用户摘要都带 `certification`，前端在姓名旁展示认证 badge；
- 认证不改变用户能做什么，只改变身份展示。

### 订单申请审批

```text
open --申请接单 + 发布者通过--> in_progress --申请交付 + 发布者通过--> completed
open --发布者取消--> cancelled
```

- 接单：任何登录用户可对非自己发布的 open 订单提交 accept 申请；发布者（或 admin）通过后订单
  进入 in_progress，接单者写入 `engineer_id`，同订单其它 pending 接单申请自动驳回；
- 交付：接单工程师对 in_progress 订单提交 delivery 申请；发布者（或 admin）通过后订单完成并结算，
  同订单其它 pending 交付申请自动驳回；
- 驳回可填理由，申请人可撤回自己 pending 的申请；接单者不能单方面取消已接订单；
- 发布者取消 open 订单时退款并自动驳回 pending 接单申请；
- 审批与状态变更、钱包结算同一事务，账单仍以 `wallet_transactions` 为准。

### 新页面与接口

- `GET /api/v1/fde/orders/assigned`（我接到的）、`GET /api/v1/fde/applications/mine`、
  `GET /api/v1/fde/applications/received`；申请创建/通过/驳回/撤回各自独立端点；
- 前端侧边栏 FDE 组新增「我接到的」「我的申请」；大厅、我发布的、我接到的分别提供申请接单、
  取消/确认交付、提交日志/申请交付操作；
- 管理员编辑用户：姓名、邮箱、启用状态、认证；余额调整走独立的
  `POST /api/v1/admin/users/{id}/wallet-adjustments`，只写 `adjustment` 流水，不直接改余额。

## 代价与后续

- 所有登录用户都能发布和申请接单，平台不再用角色限制业务范围，风控依赖余额与认证标识；
- 申请是单轮审批，没有多轮议价/合同附件；后续若需要报价与合同，可在申请模型上扩展；
- 存量角色迁移写在幂等种子里（init 每次执行），`alembic upgrade` 本身不处理数据迁移；
- 管理员编辑不支持修改用户名与重置密码，仍保持最小管理面；
- 余额调整只记录流水，没有二次复核/审计页；`adjustment` 不计入钱包的“累计用量”。
