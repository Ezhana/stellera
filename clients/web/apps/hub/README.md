# STELLERA HUB 控制台（Web）

STELLERA HUB 的 Console 前端：登录页 + 控制台外壳，视觉使用 `@ezhana/design-theme-obsidian`
（Obsidian & Gold 黑金商务风、Inter 正文 + Playfair Display 标题、暗色单模式）。页面通过前端内的 BFF/页面模型层消费后端数据，
组件不直接绑定后端 DTO 或原始权限字段。

当前范围是登录/注册与身份、平台简介、FDE 订单（大厅 / 我发布的 / 我接到的 / 我的申请 / 订单详情）、
钱包（余额 / 用量 / 充值 / 兑换码）、个人信息与公开主页、以及超级管理员的管理后台
（用户 / 认证审核 / 兑换码 / 系统设置）。
角色为 `member`（注册即会员）、`realname` / `enterprise` / `engineer`（认证身份，前端展示认证 badge）
与 `admin`；所有登录用户都能发布订单、申请接单和申请交付，接单/交付由订单发布者审批。
页面全部通过 BFF/页面模型层消费后端数据，组件不直接绑定后端 DTO 或原始权限字段。
钱包与 FDE 的资金闭环（发布扣款、取消退款、交付结算）在 `hub-api` 中实现，前端只负责展示与操作。
更完整的架构取舍见 [`docs/adr/0002-frontend-bff-page-models.md`](../../../docs/adr/0002-frontend-bff-page-models.md)。

## 技术栈

- Vue 3.5 + TypeScript + Vite 8
- vue-router 5（history 模式）、Pinia 4
- zod 4（登录表单校验 + BFF 响应校验）
- Obsidian 主题包：`@ezhana/design-theme-obsidian`、`@ezhana/design-tokens`、`@ezhana/theme`
- 单元测试：Vitest 5 + @vue/test-utils + jsdom

## 目录

```text
src/
├── models/                 # 稳定的页面模型（前端拥有，不出现后端字段）
│   ├── identity.ts         # ViewerProfile / SessionView / 多认证 Certification / 权限分组
│   ├── nav.ts              # 前端拥有的两级导航树 + navForViewer（管理组仅 admin）
│   ├── orders.ts           # FDE 订单 / 接单与交付申请 / 订单详情页面模型
│   ├── wallet.ts           # 钱包汇总 / 流水 / 兑换结果页面模型
│   ├── admin.ts            # 管理后台用户 / 认证审核 / 兑换码 / 系统设置页面模型
│   ├── profile.ts          # 个人资料 / 公开主页 / 合作记录 / 认证申请页面模型
│   └── icons.ts            # UiIcon 支持的图标名
├── bff/                    # 前端 BFF：DTO 校验、映射、聚合、错误归一化
│   ├── auth/               # AuthBff：注册/登录/恢复/刷新/登出 + SessionView
│   ├── orders/             # OrdersBff：订单大厅、发布、申请/审批、日志、我接到的、订单详情、WebSocket
│   ├── wallet/             # WalletBff：钱包汇总、流水分页、兑换码入账
│   ├── profile/            # ProfileBff：本人资料、公开主页、合作记录、认证申请
│   ├── admin/              # AdminBff：用户编辑/余额调整、认证审核、角色目录、兑换码、系统设置
│   ├── certification.ts    # 角色/接口 certifications 归一化
│   ├── token-provider.ts   # 各 feature BFF 共用的 access token 端口
│   ├── permissions.ts      # 前端权限匹配（keyMatch2/regex 子集）
│   ├── describe.ts         # 原始 policy -> 中文分组/动作标签
│   └── errors.ts           # BffError 稳定错误码（context：login/session/refresh/orders/wallet/profile/admin）
├── components/identity/    # CertificationMark 多认证 Badge
├── components/orders/      # 订单表格、申请接单弹窗、工作日志/交付申请抽屉
├── components/ui/          # Obsidian 组件层（Button/Input/Card/Chip/Alert/Modal/Drawer/Icon…）
├── layouts/                # AuthLayout（品牌面板 + 表单）、ConsoleLayout（侧栏 + 内容）
├── pages/                  # Login / Register / PlatformIntro / fde/* / wallet/* / profile/* / admin/* / NotFound
├── router/index.ts         # 路由与登录守卫（bootstrap + redirect + requiresAdmin）
├── stores/auth.ts          # 很薄的会话状态：只持有 SessionView
├── lib/http.ts             # 通用 JSON transport：ApiError、超时、base URL
├── lib/money.ts            # 金额（分→元）与时间展示的共享格式化
└── theme/                  # Obsidian 注册表与主题管理器
```

## BFF 与页面模型

数据流：

```text
FastAPI DTO
  ↓  feature gateway（zod 校验、字段容错）
feature BFF（token 注入、请求编排、错误归一化）
  ↓  mapper
页面模型（WalletSummaryView / AdminUserView / FdeOrderView …）
  ↓  Pinia store 只持有 SessionView
页面与 Ui* 组件
```

约束：

- **后端字段名只出现在各 feature 的 `bff/*/dto.ts`**；页面、组件、store 不 import 原始 DTO。
- **页面不直接使用 `fetch` / `ApiError` / localStorage**；这些由 BFF 收口。
- 每个 BFF 的 gateway 都是端口：未来接独立服务端 BFF 时实现同一个接口即可，service、store 和页面不需要改。
- BFF 对缺失/空值字段做兜底：展示名按昵称→实名→用户名回退，`email` 空串归一为 `null`，
  未知交易类型 / 兑换码状态 / 角色都有降级标签，后端新增枚举值不会让页面崩溃。
- 权限展示不直接渲染正则：`permissions.ts` + `describe.ts` 把 `/api/v1/wallet`、
  `^(GET|POST)$` 这类 policy 映射为「钱包 · 查看/创建」，原始路径只作为次要信息保留。
- `HubCapabilities` 由 auth BFF 用权限探针派生（发布订单、申请订单、日志、钱包、兑换码、管理后台），页面只分支布尔值。
- 认证标识：`CertificationMark` 接收 `certifications` 数组（realname / enterprise / engineer），
  用于侧边栏、订单发布者/接单工程师、管理端用户、认证审核与申请列表。
- 导航树由前端拥有，`navForViewer({ isAdmin })` 过滤 `requiresAdmin` 分组；
  管理端路由带 `requiresAdmin` meta，非 admin 会被守卫重定向回 `/intro`。

## 个人信息与认证

- `/profile` 个人信息页：资料编辑（昵称/邮箱/介绍/技能/城市/联系方式）、认证申请与历史、
  合作记录（已完成订单的统计与明细）；
- `/profiles/:id` 公开主页：昵称/介绍/技能/城市/认证/合作记录，隐藏实名与联系方式；
- 认证申请按类型动态表单（实名 / 企业 / 工程师），企业/工程师需先实名；被驳回可重提；
- `/admin/certifications` 认证审核页：筛选、查看完整资料、通过/驳回并刷新；
- `/fde/orders/:id` 订单详情页：订单信息、双方公开资料、日志、全部申请与审批人/时间/理由，并按权限提供操作。

## 主要交互组件

- 导航「平台 → 模型广场」是外链入口：默认新标签页打开当前主机 3000 端口的 new-api `/pricing` 页面，
  地址可用 `VITE_MODEL_SQUARE_URL` 覆盖（覆盖时需包含路径）；
- `/fde/publish` 发布需求独立页面；「我发布的」不再含内联表单，订单大厅与我发布的都链接到该页；
- 申请接单：`ApplyOrderModal` 确认弹窗 + 可选备注（≤500 字），订单大厅与订单详情共用；
- 右侧抽屉：`UiDrawer` 用于用户管理编辑（资料 + 余额调整）、提交工作日志（`WorkLogDrawer`）、
  申请交付（`DeliveryApplicationDrawer`）；
- `UiModal` / `UiDrawer` 均 Teleport 到 body，支持 ESC/遮罩关闭、body 滚动锁与焦点恢复；
  表单校验、loading、错误提示沿用页面组件。

## 本地开发

```bash
# 在 clients/web 下执行（pnpm 版本由 corepack 固定为 12.4.2）
pnpm install
pnpm --filter hub dev         # 开发服务器，默认 http://localhost:5173
pnpm --filter hub type-check  # vue-tsc
pnpm --filter hub test        # vitest run（jsdom，无网络请求）
pnpm --filter hub build       # 类型检查 + vite build，产物在 apps/hub/dist
pnpm --filter hub preview     # 预览构建产物
```

开发与预览服务器都把 `/api` 代理到 `http://127.0.0.1:8000`，因此本地启动 FastAPI 后端即可联调。

## 环境变量

复制 `.env.example` 为 `.env.local` 按需覆盖：

| 变量                    | 默认值                | 说明                                                                            |
| ----------------------- | --------------------- | ------------------------------------------------------------------------------- |
| `VITE_API_BASE_URL`     | `/api`                | API 前缀，最终 base URL 是 `${VITE_API_BASE_URL}/v1`；可填完整 URL。            |
| `VITE_MODEL_SQUARE_URL` | 当前主机:3000/pricing | 模型广场（new-api 定价页）完整地址；留空时按当前主机拼接 3000 端口 `/pricing`。 |

## 认证约定

后端契约（FastAPI，RBAC；前端由 BFF 消费）：

| 方法 | 路径                    | 请求 / 响应                                                                                                       |
| ---- | ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| POST | `/api/v1/auth/register` | `{username, email, password}` → 201，注册即 member、昵称自动生成，返回与登录同构的会话。                          |
| POST | `/api/v1/auth/login`    | `{username, password}` → `{access_token, refresh_token, token_type, expires_in, user}`。                          |
| POST | `/api/v1/auth/refresh`  | `{refresh_token}` → 新的 token pair。                                                                             |
| GET  | `/api/v1/auth/me`       | Bearer token → `user {id, username, nickname, email, full_name, is_active, roles, certifications, permissions}`。 |
| POST | `/api/v1/auth/logout`   | `{refresh_token}`，尽力而为地吊销刷新令牌。                                                                       |

会话行为（由 `AuthBff` 负责）：

- 登录时勾选「保持登录」则 token 存 `localStorage`，否则存 `sessionStorage`；注册成功后自动登录（会话）；
- 路由守卫首次导航调用 `auth.bootstrap()`：先请求 `/me`，遇到 401 时只尝试一次 `/refresh`，
  再失败就清空会话；未登录访问受保护路由会重定向到 `/login?redirect=<原路径>`；
- 已登录访问 `/login` 会跳转 `/intro`；`redirect` 只接受单斜杠开头的站内路径，防止开放重定向；
- 退出登录先尽力调用 `/logout` 吊销 refresh token，无论成败都清空本地会话；
- 错误统一为 `BffError`（`invalid-credentials` / `forbidden` / `not-found` / `conflict` /
  `invalid-input` / `network` / `server` / `session-expired` / `malformed-response`），
  页面按稳定错误码选择中文文案。

## 主题与样式

- `index.html` 固定 `lang="zh-CN"` 与 `data-theme="obsidian"`，不加载 localStorage 主题引导脚本；
- `theme/registry.ts` 只注册 Obsidian，`manager.ts` 传入 `themeModes` 与 `defaultMode: 'dark'`；
- Obsidian 自带 Inter + Playfair Display，并在字体栈内配置中文回退（正文 PingFang / 雅黑，标题 Songti）；
  `assets/app.css` 不覆盖字体栈，也不覆盖任何 `--color-*` 语义 token；
- `components/ui/` 按 Obsidian `docs/DESIGN.md` 的配方实现：24K 金渐变主按钮（每屏最多一个）、
  obsidian 近黑表面、4/6/14/20/28px 圆角、1px 发丝层级、44px 输入框、pill 徽章；
  `shadow-glow` 只留给这一个金色焦点；
- 状态 badge 直接使用语义状态色；金色 badge 使用 Obsidian 文档的 gold-300 `#E8D189`，
  连同金色渐变、strong hairline、inset highlight 等组件层值以 `--obsidian-*` 定义在 `app.css`。

## Docker

构建上下文是 workspace 根 `clients/web`，用通用 Dockerfile 的 `APP` 参数选择应用：

```bash
docker build -f clients/web/Dockerfile --build-arg APP=hub clients/web
docker run --rm -p 8080:80 <image>
```

镜像内用 nginx 托管 `dist`：`nginx.conf` 提供 SPA history 回退，并把 `/api/` 代理到
compose 网络中的 `api:8000`。单独 `docker run` 只适合验证静态站点；带后端与数据库的
完整环境请用根目录 `deploy/compose.yaml`（`just up`）。构建期可用
`--build-arg NODE_IMAGE=...` / `--build-arg NGINX_IMAGE=...` 覆盖基础镜像；
内网 npm 源用 `--build-arg NPM_REGISTRY=...`（corepack 下载 pnpm 的源单独用
`--build-arg COREPACK_NPM_REGISTRY=...`，不填时复用 `NPM_REGISTRY`），留空均为官方 registry。
