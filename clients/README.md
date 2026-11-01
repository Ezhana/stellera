# clients/

面向用户的客户端应用放在这里：web、desktop、mobile，以及某个客户端专属的 bff 边缘层。每个子目录是一个独立的 Nx 项目。

## 放什么

- 用户直接使用的应用：`clients/web`、`clients/desktop-admin`、`clients/mobile-app`
- 某个客户端专属的边缘层：`clients/bff-gateway`
- 客户端之间显式抽出的共享 library：`clients/web-shared-ui`

后端服务、部署编排、跨语言契约都不在这里：分别在 `services/`、`deploy/`、`services/contracts`。

## 当前项目

### `clients/web` — 前端工作区（Nx 项目名 `web`）

由 [Ezhana/frontend-template](https://github.com/Ezhana/frontend-template) 生成的前端项目，直接以目录形式并入本仓库（同一份 Git 历史，没有嵌套仓库）。它本身是一个 pnpm workspace，所以目录内部有 `apps/` 与 `packages/` 两级：

```text
clients/web/
├── project.json            # Nx 项目定义：name = web
├── package.json            # workspace 根：脚本、engines、packageManager
├── pnpm-workspace.yaml     # apps/* 与 packages/* 两个 workspace
├── pnpm-lock.yaml
├── apps/
│   └── hub/                # Vue 3 + Vite 客户端（Obsidian 黑金 FDE 交付控制台 + BFF 页面模型，产物 apps/hub/dist）
├── packages/               # 共享的 ESLint / Prettier 配置包
└── README.md               # 前端工作区自己的说明
```

- 依赖安装：`cd clients/web && pnpm install`（pnpm 版本由 `packageManager` 字段锁定，用 corepack 自动取用）。
- 本地开发：`cd clients/web && pnpm dev`，或按根 README 临时装好 Nx 后用 `npx nx run web:serve`。
- 构建与校验：装好 Nx 后 `npx nx run web:build` / `web:lint` / `web:test` / `web:typecheck`，也可以直接进目录用 `pnpm lint`、`pnpm build`。
- 产物 `apps/hub/dist`、`node_modules/`、`.codegraph/` 都不提交，忽略规则见根 `.gitignore` 与 `clients/web/.gitignore`。
- 提交钩子：`pnpm install` 时 `simple-git-hooks` 会把 pre-commit 写进根仓库的 `.git/hooks/`；钩子命令会先切到 `clients/web` 再跑 `lint-staged`，只处理该目录下的暂存文件，不影响仓库其它部分。

## 命名与结构

目录名通常是 `<platform>-<name>`，platform 取 `web`、`desktop`、`mobile`、`bff`，Nx 项目名与目录名一致。`clients/web` 是已接入的前端工作区，项目名就叫 `web`；后续加单个客户端时按 `<platform>-<name>` 建目录即可。

| platform | 示例目录（按需创建） | 常见 targets |
| --- | --- | --- |
| web | `clients/web`（已接入）/ `clients/web-portal` | serve / build / e2e / lint / test |
| desktop | `clients/desktop-admin` | serve / build / lint / test |
| mobile | `clients/mobile-app` | serve / build / e2e / lint / test |
| bff | `clients/bff-gateway` | serve / build / lint / test |

```text
clients/
└── web/                        # 已接入：pnpm workspace + Nx 项目 web
    ├── project.json
    ├── apps/hub/               # 实际的客户端应用
    ├── packages/               # 工作区内部共享配置
    └── README.md
```

共享 library 的结构相同，`projectType` 写成 `library`。

## 接入 Nx

每个项目靠自己的 `project.json` 被 Nx 自动发现。根目录没有项目清单，也没有 `package.json`；加一个客户端就是建目录、在其中放 `project.json`，根配置保持不动，`nx show projects` 里就会出现它。

```json
{
  "name": "web",
  "projectType": "application",
  "sourceRoot": "clients/web/apps/hub/src",
  "targets": {
    "serve": { "executor": "nx:run-commands", "options": { "command": "pnpm run dev", "cwd": "clients/web" }, "cache": false },
    "build": { "executor": "nx:run-commands", "options": { "command": "pnpm run build", "cwd": "clients/web" }, "outputs": ["{projectRoot}/apps/*/dist"] },
    "lint": { "executor": "nx:run-commands", "options": { "command": "pnpm run lint", "cwd": "clients/web" } },
    "test": { "executor": "nx:run-commands", "options": { "command": "pnpm -r --if-present run test", "cwd": "clients/web" } },
    "typecheck": { "executor": "nx:run-commands", "options": { "command": "pnpm -r --filter \"./apps/*\" --if-present run type-check", "cwd": "clients/web" } }
  }
}
```

target 名沿用 `lint`、`test`、`build`、`e2e`、`typecheck`、`serve`：`nx.json` 按这些名字配置缓存与顺序，`build` 会先跑上游依赖的 `build`，`serve` 是常驻进程、不缓存。`test` 目前没有用例，`pnpm -r --if-present` 会正常空跑；等 apps 里补上 `test` 脚本后自动开始执行。

## 与相邻目录的关系

- `services/` 提供后端与契约；客户端消费 `services/contracts` 经 `tools/gen-api` 生成的代码。
- `deploy/` 消费 Nx 构建产物；`bff-*` 的部署形态接近服务，归属仍是某个客户端。
- CI 入口是 `.github/workflows/ci.yml`，用 `nx affected` 跑受影响的项目；`clients/web` 自带的 pnpm lockfile 由 CI 用 `--frozen-lockfile` 安装。
