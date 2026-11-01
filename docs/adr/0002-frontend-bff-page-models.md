# 0002 — 前端 BFF 与稳定页面模型

- 状态：已采纳
- 日期：2026-11-02

## 背景

登录模块最初由页面直接调用 `/api/v1/auth/*`：Pinia store 持有后端 `AuthUser`，登录页和
Console 页面直接读取 `full_name`、`permissions[].object/action` 等字段，并自己解释 HTTP 状态码。
随着钱包、订单、广场等模块接入，这会带来三个问题：

1. 后端 DTO 一改，页面、store、测试全部跟着改；页面没有稳定的“页面模型”。
2. 后端返回的是原始 Casbin policy（`/api/v1/wallet/*`、`^(GET|POST)$`），不是业务文案；
   页面要自己解析正则、分组和降级。
3. 登录/刷新/token 存储/错误码散落在页面和 store 里，无法替换传输层，也不方便统一测试。

同时把前端主题切换到 Obsidian（黑金商务风），需要一个与主题解耦、可复用的 `components/ui/`
组件层，而不是继续使用 Quest 命名的组件。

## 决策

### 1. 前端内 BFF 层

在 `src/bff/` 增加一层前端 BFF，数据流固定为：

```text
lib/http.ts (transport)
  → bff/auth/gateway.ts (AuthGateway 端口 + HttpAuthGateway)
  → bff/auth/service.ts (AuthBff：token、refresh、错误归一化)
  → bff/auth/mapper.ts (DTO → ViewerProfile)
  → models/ (稳定页面模型)
  → stores/auth.ts (只持有 SessionView)
  → pages/ + components/ui/
```

- **后端字段名只允许出现在 `bff/auth/dto.ts` 的 zod schema 中。** 其余层使用 camelCase 的
  前端模型。
- **页面/组件不直接使用 `fetch`、`ApiError`、localStorage。** token 持久化和刷新只在
  `AuthBff` 内；页面只看到 `SessionView`。
- `AuthGateway` 是端口。当前是 `HttpAuthGateway`（直连 FastAPI）；未来增加独立服务端 BFF 时，
  实现同一个接口即可替换，`AuthBff`、store、页面无需改动。
- 传输/响应错误统一成 `BffError` 的稳定错误码：
  `invalid-credentials` / `forbidden` / `network` / `server` / `session-expired` /
  `malformed-response` / `unknown`。页面只按错误码选择文案。

### 2. 稳定页面模型

`src/models/` 定义前端拥有的模型：

- `ViewerProfile`：`id`（统一为 string）、`displayName`（`full_name` 为空回退 `username`）、
  `email`（空串归一为 `null`）、`initials`、`statusLabel`、角色标签、权限分组、
  `permissionCount`、`moduleAccess`。
- `SessionView`：`viewer + remember + authenticatedAt`，**不包含 token**。
- `ConsolePageModel`：`viewer + modules + permissionGroups + summary`，由
  `buildConsolePageModel` 聚合。
- `modules.ts` 是前端维护的模块目录（钱包/订单/广场），后端不决定名称、顺序、描述、可用状态。

映射/兜底规则：

- 缺失的 `roles`/`permissions` 默认为空数组；
- `full_name` 为空 → `username`；中文名截前两字、英文名取词首作为头像 initials；
- 未知角色保留 key 并用默认 tone；未知权限对象归入「其他接口」；
- 原始 policy 被映射为业务分组和动作标签（`钱包`、`查看/创建/全部操作`），原始路径只作为
  次要信息展示。

### 3. Console 页面聚合

`buildConsolePageModel(viewer)` 把后端派生能力与前端模块目录合并：

- 用 `permissionAllows`（keyMatch2/regex 子集）对每个模块的 probe path 检查读/写；
- 生成 `moduleAccess: 'write' | 'read' | 'none'`、`accessLabel`、`accessTone`；
- 生成 `ConsoleSummary`（角色数、权限项、可读/可写模块数）；
- 模块 `availability` 由前端维护（当前统一为 `planned/即将上线`）。

### 4. Obsidian 黑金主题与组件层

- 主题从 Quest 切换到 `@ezhana/design-theme-obsidian`：`data-theme="obsidian"`、Inter + Playfair Display、
  obsidian 近黑/象牙/24K 金、4/6/14/20/28px 圆角、黑 alpha 阴影；`shadow-glow` 只留给每屏唯一的金色焦点（主按钮/CTA）。
- `components/quest/*` 重命名为与主题无关的 `components/ui/Ui*`，按 Obsidian
  `docs/DESIGN.md` 的组件配方实现；组件只消费语义 token，不为某个页面写一次性样式。
- 字体（Inter / Playfair + 中文 PingFang / Songti）由 Obsidian 主题自带；`assets/app.css` 只定义
  Obsidian 文档中的组件层值（金色渐变、strong hairline、inset highlight、gold-300 文本色），
  不覆盖主题的 `--color-*` 与字体栈。

## 代价

- 前端多了一层映射代码和测试（BFF 映射、权限匹配、页面模型），但后端字段变化不再穿透到页面。
- 页面模型是前端契约，需要和产品/后端保持沟通；未知后端字段会被 zod 忽略，新增字段需要
  显式加入 DTO 和模型。
- token 仍存在浏览器 localStorage/sessionStorage，XSS 可读；当前 BFF 是前端内适配层，不是
  服务端 BFF。要真正隐藏 token，需要后续引入服务端 BFF + httpOnly cookie。

## 被否掉的方案

| 方案 | 否决原因 |
| --- | --- |
| 页面直接调用 API、直接渲染后端字段 | 后端 DTO/policy 变化会穿透整个前端，且页面承担正则/错误码解析 |
| 先在页面里做零散 `computed` 映射 | 无法复用、难测试，模块多了会重复 |
| 立即新建独立 Node BFF 服务 | 当前范围只需要前端稳定的页面模型；先用 `AuthGateway` 端口隔离，后续可无缝替换 |
| 继续使用 Quest 组件改名 | 主题已切 Obsidian，组件配方、字体、圆角、阴影、状态色都不同，必须按 Obsidian 重做 |

## 后续

- 钱包/订单/广场接入时，按同一模式新增 `bff/<module>` + `models/<module>`，页面只消费模型。
- 如需服务端 BFF，实现 `AuthGateway` 并替换 `authBff` 的 gateway；可同时把 token 改到
  httpOnly cookie。
- 权限管理 UI 可用 `describe.ts` 的反向映射（业务标签 → policy）作为起点。
