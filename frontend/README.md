# ChongMing Frontend

`frontend/` 是重明平台的 Web UI，基于 Next.js App Router 构建。它负责模块导航、测试设计、执行调度、视觉 UI 用例、API 自动化、性能压测、智能运维、模型治理和系统设置页面。

## 技术栈

| 类别 | 技术 |
|---|---|
| 框架 | Next.js 16.1.6 |
| UI | React 19.2.3、TypeScript |
| 样式 | Tailwind CSS 4、tailwind-merge、tw-animate-css |
| 组件 | Radix UI、shadcn 风格组件、lucide-react |
| 数据请求 | fetch、axios、TanStack Query |
| 可视化 | Recharts、react-compare-slider、JSON View |

## 目录结构

```text
src/
├── app/                    # App Router 页面和全局布局
├── components/             # 业务组件和通用 UI 组件
├── services/               # 后端 API 客户端
└── lib/                    # 工具函数
```

## 页面路由

侧边栏定义在 `src/components/Sidebar.tsx`。

| 路由 | 页面文件 | 说明 |
|---|---|---|
| `/` | `src/app/page.tsx` | 总览大盘 |
| `/design` | `src/app/design/page.tsx` | 需求解析、场景生成 |
| `/executions` | `src/app/executions/page.tsx` | 执行调度、状态轮询、结果抽屉 |
| `/visual-ui` | `src/app/visual-ui/page.tsx` | 视觉 UI 用例列表和编辑入口 |
| `/visual-ui/scenario/[id]` | `src/app/visual-ui/scenario/[id]/page.tsx` | 单个视觉场景编辑/执行 |
| `/api-auto` | `src/app/api-auto/page.tsx` | API 自动化请求构造和执行 |
| `/performance` | `src/app/performance/page.tsx` | 性能压测入口 |
| `/turbo` | `src/app/turbo/page.tsx` | Turbo 压测页面 |
| `/smart-ops` | `src/app/smart-ops/page.tsx` | 缺陷分析、历史缺陷、智能运维 |
| `/model-config` | `src/app/model-config/page.tsx` | 模型治理、模型配置、Token 指标 |
| `/phoenix` | `src/app/phoenix/page.tsx` | 凤凰涅槃、脚本固化与回归治理 |
| `/settings` | `src/app/settings/page.tsx` | 系统设置 |

## 服务层

通用 API 客户端在 `src/services/api.ts`：

```ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
```

| 文件 | 后端前缀 | 说明 |
|---|---|---|
| `dashboardService.ts` | `/dashboard` | 总览 KPI、趋势、缺陷分布、近期活动 |
| `executionsService.ts` | `/executions` | 执行结果查询 |
| `visualUiService.ts` | `/visual-ui`、`/executions` | 视觉用例 CRUD、从设计导入、临时执行 |
| `apiAutoService.ts` | API 自动化相关端点 | 请求构造、响应展示、API 自动化 |
| `environmentService.ts` | `/environments` | 环境变量和 base URL 管理 |
| `phoenixService.ts` | `/phoenix` | 轨迹编译、脚本治理、回归相关操作 |
| `smartOpsService.ts` | `/smart-ops` | 模型列表、模块配置、Provider Key、Token 指标、缺陷分析 |
| `turboService.ts` | `/api/v1/turbo` | 启动/停止压测、查询压测统计 |

注意：大多数服务通过 `api.ts` 访问完整 `/api/v1` 基址；`turboService.ts` 使用 axios，默认 `NEXT_PUBLIC_API_URL || http://localhost:8000`，然后拼接 `/api/v1/turbo/*`。

## 前端调用链

### 总览大盘

```text
src/app/page.tsx
  -> dashboardService.getDashboardOverview()
  -> GET /api/v1/dashboard/overview
  -> 展示 KPI、趋势、缺陷分布、近期活动
```

### 执行调度

```text
src/app/executions/page.tsx
  -> fetch /api/v1/test-cases?page=1&page_size=100
  -> 用户选择用例和环境
  -> POST /api/v1/executions
  -> React Query 每 2 秒轮询 GET /api/v1/executions?skip=&limit=
  -> 打开 ExecutionDrawer 查询 GET /api/v1/executions/{id}/result
```

### 视觉 UI

```text
src/app/visual-ui/page.tsx
  -> visualUiService.getCases/createCase/updateCase/deleteCase
  -> /api/v1/visual-ui/cases
  -> 场景页可通过 visualUiService.executeAdhoc()
  -> POST /api/v1/executions with dynamic_payload
```

### 性能压测

```text
src/app/performance/page.tsx 或 src/app/turbo/page.tsx
  -> turboService.startStressTest()
  -> POST /api/v1/turbo/run
  -> turboService.getTestStats()
  -> GET /api/v1/turbo/stats/{test_id}
  -> turboService.stopStressTest()
  -> POST /api/v1/turbo/stop/{test_id}
```

### 智能运维和模型治理

```text
src/app/smart-ops/page.tsx / src/app/model-config/page.tsx
  -> smartOpsService
  -> /api/v1/smart-ops/models
  -> /api/v1/smart-ops/config
  -> /api/v1/smart-ops/provider
  -> /api/v1/smart-ops/analyze-defect
  -> /api/v1/smart-ops/defects
```

## 本地开发

```bash
cd frontend
npm install
npm run dev
```

默认访问：`http://localhost:3000`。

如后端不在默认地址，创建 `.env.local`：

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
```

如果某个服务文件使用 axios 并自行拼接 `/api/v1`，则 `NEXT_PUBLIC_API_URL` 应配置为后端根地址，例如：

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

修改这类服务前需要确认拼接方式，避免出现 `/api/v1/api/v1`。

## 脚本

| 命令 | 说明 |
|---|---|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 生产构建 |
| `npm run start` | 启动生产构建 |
| `npm run lint` | ESLint 检查 |

## UI 约定

- 通用组件放在 `src/components/ui/`。
- 模块组件放在对应业务目录，例如 `src/components/visual-ui/`、`src/components/api-auto/`。
- 页面级数据请求优先集中在 `src/services/`；少量页面内 fetch 需要与后端路径保持同步。
- 长任务页面使用轮询或后端返回的 task/execution id，不在前端假设任务已立即完成。

## 与后端的对应关系

| 前端模块 | 后端端点 | 后端服务/引擎 |
|---|---|---|
| Design | `/api/v1/design` | `services/neural_design`、`tasks/design_tasks.py` |
| Executions | `/api/v1/executions` | `ExecutionService`、`execute_test_cases`、`Dispatcher` |
| Visual UI | `/api/v1/visual-ui` | `VisualUIService`、`MidsceneAdapter`、Midscene Runner |
| API Auto | `/api/v1/api-engine`、`/api/v1/left-pupil` | `services/left_pupil`、`LeftPupilEngine` |
| Performance/Turbo | `/api/v1/turbo` | `TurboEngine`、Locust |
| Phoenix | `/api/v1/phoenix` | `services/phoenix`、`tasks/phoenix_tasks.py` |
| Smart Ops/Model Config | `/api/v1/smart-ops` | `services/smart_ops`、AI Client、Milvus |
| Overview | `/api/v1/dashboard` | dashboard endpoint、数据库和健康探针 |
