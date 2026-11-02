# 前端 Monorepo 模板

[English](./README.md) | 简体中文

> **当前所在位置：** 本目录是 Stellera monorepo 的 `clients/web` —— 与根目录同属一个 Git 仓库，
> 没有嵌套仓库；根目录通过 `just` 驱动它（见 `clients/README.md`）：在仓库根目录跑
> `just frontend-install` / `just frontend-dev` 等 recipe，或在本目录直接跑下面的 pnpm 命令。
> 下面的 pnpm workspace、lockfile 与共享配置自成一体，目录单独使用也能工作（不依赖根目录工具）；
> `apps/hub` 是用本模板生成的 Vue 3 + Vite 应用。

由 `frontend-template-source` 生成的 pnpm workspace 启动模板。模板本身默认**不包含应用**；通过
**Use this template** 或直接 clone 后，用一行命令选择 React 或 Vue：

```bash
pnpm create:app
```

命令会询问框架和应用名，调用官方 `create-vite` / `create-vue` 生成项目，套用主题集成（传
`--no-theme` 可保留官方脚手架原样），最后把应用安装到 `apps/<name>`。生成器本身是已发布的
`create-ezhana-app` 包，以普通 devDependency 精确锁定，随 workspace 一起版本化和审计。非交互用法：

```bash
pnpm create:app react my-app
pnpm create:app vue my-app

# 创建时写入组合共享包的轻量 ESLint/Prettier 配置
pnpm create:app react my-app --eslint --prettier

# 保留官方脚手架原样，不套用主题覆盖
pnpm create:app react my-app --no-theme

# 或稍后配置已有应用
pnpm create:app configure apps/my-app --eslint --prettier
```

生成的应用默认保留官方脚手架自己的 lint/format 工具链，除非显式选择共享配置。应用共用根目录的
提交钩子和 CI 配置。

## 环境要求

- Node.js 24
- pnpm 12
- 首次使用前执行一次 `pnpm install`，它会安装根目录工具和固定版本的生成器
- 首次执行 `pnpm create:app` 需要网络（会下载官方脚手架和 npm 包）

## 使用方式

```bash
pnpm install          # 安装根目录工具和固定版本的 create-ezhana-app 生成器
pnpm create:app       # 选择 React 或 Vue，并输入应用名
pnpm dev              # 运行已生成的应用
pnpm build            # 构建已生成的应用
pnpm lint
pnpm check            # format:check + lint + build
```

也可以直接使用 workspace filter：

```bash
pnpm --filter ./apps/my-app dev
pnpm --filter ./apps/my-app build
```

## Lint 与格式化

lint/format 规则位于 `packages/` 下的共享 workspace 包中：`eslint-config-base`、
`eslint-config-typescript`、`eslint-config-react`、`eslint-config-vue` 和 `prettier-config`。根目录的
`eslint.config.mjs` 引入 `@ezhana/eslint-config-base`，根目录的 `prettier.config.mjs` 重新导出
`@ezhana/prettier-config`，因此在 `packages/` 中修改规则会作用于 workspace 根目录。

默认情况下 `create:app` 不改动脚手架的 lint/format 设置：React 应用保留 Vite 生成的 Oxlint 配置，
Vue 应用默认没有 lint/format 设置。如需把共享配置写入应用，可在创建时传 `--eslint` /
`--prettier`，或稍后执行：

```bash
pnpm create:app configure apps/my-app --eslint --prettier
```

`configure` 写入的是轻量配置：应用的 `eslint.config.mjs` 引入
`@ezhana/eslint-config-<framework>`（并提供应用级覆盖的扩展点），应用的 `prettier.config.mjs` 重新
导出 `@ezhana/prettier-config`。它会通过 `pnpm add -D` 以 `workspace:*` 把配置包加入应用的依赖。
它不会删除 Oxlint，也不会修改 `package.json` 脚本；如果需要 `pnpm lint` 使用 ESLint，请自行调整
脚本。

如需为所有应用修改规则，请修改对应的 `packages/eslint-config-*/index.js`（或
`packages/prettier-config/index.js`），或在单个应用的配置中添加覆盖。

## 共享包

`packages/` 包含共享的 lint/format 配置包（即上文的五个配置包）。它们是 workspace 包而不是已发布的
npm 依赖：根目录和应用的配置通过 workspace 解析它们，因此请保留该目录及这些包。

可以在它们旁边添加自己的共享包：

- 创建 `packages/<name>`，包含 `package.json`、`src/` 和构建脚本；
- 在应用中通过 `"workspace:*"` 引用；
- 在 `pnpm build` 之前执行 `pnpm build:packages`（配置包没有构建步骤，会被跳过）。

详见 [`packages/README.md`](packages/README.md)。

已发布的 `@ezhana/*` 主题和令牌包是普通 npm 依赖，不链接 workspace 源码。

## 主题

生成的应用（默认套用主题）从 npm 安装已发布的设计令牌、主题包与主题运行时；样式在入口文件中引入，
本地不需要构建令牌。

- `@ezhana/design-tokens` 提供核心令牌、语义契约和默认主题。
- `@ezhana/design-theme-ocean`、`@ezhana/design-theme-cerulean` 和 `@ezhana/design-theme-quest`
  是各自独立发布的主题包。QuestUI 仅提供暗色模式，因此注册表和运行时支持主题声明颜色模式的子集。
- `@ezhana/theme` 管理主题与颜色模式状态。
- 颜色模式默认跟随操作系统（`prefers-color-scheme`）。
- `data-theme` 选择主题；只有显式选择颜色模式时才写 `data-color-mode`。
- React 和 Vue 应用都会生成主题切换器。
- 创建应用时传 `--no-theme` 可跳过主题覆盖：不会加入主题运行时、切换器或 `@ezhana` 主题依赖。

每个应用在 `src/theme/registry.ts` 注册主题，并从注册表推导 `AppTheme`，因此切换器和主题管理器
始终与已安装的主题包一致：

```ts
import { defaultThemeDefinition } from '@ezhana/design-tokens'
import { theme as cerulean } from '@ezhana/design-theme-cerulean'
import { theme as ocean } from '@ezhana/design-theme-ocean'
import { defineThemeRegistry } from '@ezhana/theme'

export const themeRegistry = defineThemeRegistry([defaultThemeDefinition, ocean, cerulean])
export type AppTheme = (typeof themeRegistry.themes)[number]
```

添加主题：在应用中安装对应主题包、在入口文件中引入其样式，并把它的 `theme` 导出加入
`defineThemeRegistry([...])`。如果主题支持的颜色模式少于应用（例如仅暗色的主题），还需向
`createThemeManager` 传入 `themeModes: themeRegistry.themeModes`，以便把解析后的模式收敛到主题支持的模式。
主题包提供 `./style`（核心样式 + 主题字体（如有）+ 覆盖，一次引入即可）、
`./theme.css`（仅覆盖）和 `./standalone.css`（核心 + 覆盖，适合无 bundler 场景）。

令牌契约、主题模型与运行时 API 见 npm 包文档：

- [`@ezhana/design-tokens`](https://www.npmjs.com/package/@ezhana/design-tokens)
- [`@ezhana/theme`](https://www.npmjs.com/package/@ezhana/theme)
- [`@ezhana/design-theme-cerulean`](https://www.npmjs.com/package/@ezhana/design-theme-cerulean)
- [`@ezhana/design-theme-ocean`](https://www.npmjs.com/package/@ezhana/design-theme-ocean)
- [`@ezhana/design-theme-quest`](https://www.npmjs.com/package/@ezhana/design-theme-quest)

## CI

CI 由 Stellera monorepo 根目录的 [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) 负责：
先 `pnpm install --frozen-lockfile` 安装本工作区，再直接跑本项目自己的 pnpm 命令：`pnpm lint`、
`pnpm -r --if-present run test`、`pnpm build` 和
`pnpm -r --filter "./apps/*" --if-present run type-check`。CI 不经过根目录的任务编排层。并入
monorepo 时删掉了模板自带的 workflow —— GitHub 只读取仓库根目录的 `.github/workflows`。本地等价的
检查是 `pnpm format:check`、`pnpm lint` 和 `pnpm build`。

## License

MIT
