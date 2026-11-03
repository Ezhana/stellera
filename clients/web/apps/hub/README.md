# STELLERA HUB 控制台（Web）

STELLERA HUB 的 Console 前端：登录页 + 控制台外壳，视觉使用 `@ezhana/design-theme-obsidian`
（Obsidian & Gold 黑金商务风、Inter 正文 + Playfair Display 标题、暗色单模式）。页面通过前端内的 BFF/页面模型层消费后端数据，
组件不直接绑定后端 DTO 或原始权限字段。

当前范围是登录、身份与权限展示；钱包 / 订单 / 广场以模块卡片呈现，等待后续接入。
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
│   ├── identity.ts         # ViewerProfile / SessionView / 权限分组
│   ├── console.ts          # ConsolePageModel / ModuleView / ConsoleSummary
│   └── modules.ts          # 前端维护的模块目录（钱包/订单/广场）
├── bff/                    # 前端 BFF：DTO 校验、映射、聚合、错误归一化
│   ├── auth/
│   │   ├── dto.ts          # 唯一出现后端字段名的 zod schema
│   │   ├── gateway.ts      # AuthGateway 端口 + HttpAuthGateway 实现
│   │   ├── mapper.ts       # UserDto -> ViewerProfile，权限 -> 业务标签
│   │   ├── token-store.ts  # localStorage / sessionStorage（仅 BFF 使用）
│   │   └── service.ts      # AuthBff：登录/恢复/刷新/登出 + SessionView
│   ├── console/index.ts    # buildConsolePageModel：模块访问 + 摘要聚合
│   ├── permissions.ts      # 前端权限匹配（keyMatch2/regex 子集）
│   ├── describe.ts         # 原始 policy -> 中文分组/动作标签
│   └── errors.ts           # BffError 稳定错误码
├── components/ui/          # Obsidian 组件层（Button/Input/Checkbox/Card/Chip/Alert/BrandMark/Icon）
├── layouts/                # AuthLayout（品牌面板 + 表单）、ConsoleLayout（侧栏 + 内容）
├── pages/                  # LoginPage、ConsolePage、NotFoundPage
├── router/index.ts         # 路由与登录守卫（bootstrap + redirect）
├── stores/auth.ts          # 很薄的会话状态：只持有 SessionView
├── lib/http.ts             # 通用 JSON transport：ApiError、超时、base URL
└── theme/                  # Obsidian 注册表与主题管理器
```

## BFF 与页面模型

数据流：

```text
FastAPI DTO
  ↓  HttpAuthGateway（zod 校验、字段容错）
AuthBff（token 持久化、刷新旋转、错误归一化）
  ↓  mapper
SessionView / ViewerProfile（稳定页面模型）
  ↓  Pinia store（只存 SessionView）
ConsolePageModel（模块访问 + 权限分组 + 摘要聚合）
  ↓
页面与 Ui* 组件
```

约束：

- **后端字段名只出现在 `bff/auth/dto.ts`**；页面、组件、store 不 import 原始 DTO。
- **页面不直接使用 `fetch` / `ApiError` / localStorage**；这些由 BFF 收口。
- `HttpAuthGateway` 是端口：未来接独立服务端 BFF 时，实现同一个 `AuthGateway` 即可，
  `AuthBff`、store 和页面不需要改。
- BFF 对缺失/空值字段做兜底：`full_name` 为空用 `username`，`email` 空串归一为 `null`，
  `roles`/`permissions` 缺省为空数组，未知角色/权限有降级标签。
- 模块访问不是后端直接返回的：BFF 用前端模块目录（`models/modules.ts`）加后端权限做匹配，
  生成 `moduleAccess: { wallet/orders/plaza: 'write'|'read'|'none' }` 和业务文案。
- 权限展示不直接渲染正则：`permissions.ts` + `describe.ts` 把 `/api/v1/wallet/*`、
  `^(GET|POST)$` 这类 policy 映射为「钱包 · 查看/创建/全部操作」，原始路径只作为次要信息保留。
- `ConsolePageModel` 汇总角色数、权限项、可读/可写模块数；页面只消费这个模型。

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

| 变量                | 默认值 | 说明                                                                 |
| ------------------- | ------ | -------------------------------------------------------------------- |
| `VITE_API_BASE_URL` | `/api` | API 前缀，最终 base URL 是 `${VITE_API_BASE_URL}/v1`；可填完整 URL。 |

## 认证约定

后端契约（FastAPI，RBAC；前端由 BFF 消费）：

| 方法 | 路径                   | 请求 / 响应                                                                              |
| ---- | ---------------------- | ---------------------------------------------------------------------------------------- |
| POST | `/api/v1/auth/login`   | `{username, password}` → `{access_token, refresh_token, token_type, expires_in, user}`。 |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` → 新的 token pair。                                                    |
| GET  | `/api/v1/auth/me`      | Bearer token → `user {id, username, email, full_name, is_active, roles, permissions}`。  |
| POST | `/api/v1/auth/logout`  | `{refresh_token}`，尽力而为地吊销刷新令牌。                                              |

会话行为（由 `AuthBff` 负责）：

- 登录时勾选「保持登录」则 token 存 `localStorage`，否则存 `sessionStorage`；
- 路由守卫首次导航调用 `auth.bootstrap()`：先请求 `/me`，遇到 401 时只尝试一次 `/refresh`，
  再失败就清空会话；`/console` 未登录会重定向到 `/login?redirect=<原路径>`；
- 已登录访问 `/login` 会跳转 `/console`；`redirect` 只接受单斜杠开头的站内路径，防止开放重定向；
- 退出登录先尽力调用 `/logout` 吊销 refresh token，无论成败都清空本地会话；
- 错误统一为 `BffError`（`invalid-credentials` / `forbidden` / `network` / `server` /
  `session-expired` / `malformed-response`），页面按稳定错误码选择中文文案。

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
