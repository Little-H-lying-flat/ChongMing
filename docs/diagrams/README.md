# Architecture Diagrams

`docs/diagrams/` 保存重明平台的 Mermaid 架构图和时序图。这里的图需要和真实代码路径、API 前缀、Celery 调度和引擎调用链保持一致。

## 图谱清单

| 文件 | 类型 | 覆盖范围 | 主要代码路径 |
|---|---|---|---|
| `module-dependency.mmd` | 模块依赖图 | 前端、API、服务层、任务层、引擎层、基础设施和外部系统 | `frontend/src`、`backend/app`、`deploy/docker-compose.yml` |
| `sequence-testcase-execution-result.mmd` | 时序图 | 用例选择、执行创建、Celery/本地执行、Dispatcher 分支、结果持久化、前端查询 | `endpoints/executions.py`、`tasks/execution_tasks.py`、`services/execution_service.py` |
| `sequence-health-midscene.mmd` | 时序图 | 健康检查与 Midscene Runner 探针 | `endpoints/health.py`、`services/midscene_adapter.py` |
| `sequence-neural-design-to-execution.mmd` | 时序图 | 需求解析生成场景并交给执行链路 | `endpoints/design.py`、`services/neural_design/`、`tasks/design_tasks.py` |
| `sequence-dispatcher-branching.mmd` | 时序图 | UI/HYBRID 通过 MidsceneAdapter 执行，API 通过 Dispatcher/LeftPupil 执行 | `tasks/execution_tasks.py`、`services/midscene_adapter.py`、`engines/dispatcher.py`、`engines/left_pupil/` |
| `sequence-phoenix-compile-heal.mmd` | 时序图 | Phoenix 轨迹编译、脚本生成、自愈和回归治理 | `endpoints/phoenix.py`、`services/phoenix/`、`tasks/phoenix_tasks.py` |
| `sequence-exception-timeout.mmd` | 异常时序图 | 步骤执行超时到失败状态落库 | `tasks/execution_tasks.py`、`services/execution_service.py` |
| `sequence-exception-assertion-failure.mmd` | 异常时序图 | API 断言失败、错误信息和结果持久化 | `engines/left_pupil/`、`services/left_pupil/` |

## 当前主调用链

### 执行调度

```text
frontend/src/app/executions/page.tsx
  -> POST /api/v1/executions
  -> ExecutionService.create_execution
  -> execute_test_cases.delay 或 BackgroundTasks 本地执行
  -> UI/HYBRID: MidsceneAdapter
  -> API: Dispatcher.execute -> LeftPupilEngine
  -> ExecutionService.create_step_result / update_execution_status
  -> GET /api/v1/executions/{id}/result
```

### 需求解析

```text
frontend/src/app/design/page.tsx
  -> /api/v1/design/*
  -> DesignService / analyze_requirement_task
  -> AI Client + RAG Retriever
  -> scenarios / refined test cases
  -> Visual UI 导入或 /executions dynamic_payload
```

### 视觉 UI

```text
frontend/src/app/visual-ui/*
  -> /api/v1/visual-ui/cases
  -> VisualUIService
  -> /api/v1/executions
  -> MidsceneAdapter
  -> Midscene Runner / Playwright
```

### Turbo

```text
frontend/src/app/performance 或 frontend/src/app/turbo
  -> /api/v1/turbo/run
  -> TurboEngine
  -> Locust runner
  -> /api/v1/turbo/stats/{test_id}
```

## 维护规则

当以下内容变化时，必须同步更新对应 `.mmd`：

1. 新增、删除或重命名 API 前缀。
2. `ExecutionService`、Celery 调度或 `execute_test_cases` 的流程变化。
3. `Dispatcher`、Midscene、Left Pupil、Turbo、Phoenix 的调用链变化。
4. 健康检查、Midscene Runner 探针、向量库或外部服务依赖变化。
5. 前端页面到后端端点的映射变化。

## 校验

在仓库根目录运行：

```bash
python scripts/check_mermaid_diagrams.py
```

校验脚本会检查：

- Mermaid 文件是否为 UTF-8。
- 首行是否为支持的 Mermaid 图类型。
- 流程图是否有边。
- 时序图是否有消息箭头。
- `subgraph` / `alt` / `loop` 等块是否闭合。
- 括号是否配平。

## Mermaid 编写约定

- 节点名尽量使用真实模块名或文件名，例如 `ExecutionService`、`execute_test_cases`、`MidsceneAdapter`。
- 不在图里放过长业务文案，详细解释写到 README 或设计文档。
- 外部系统统一放在 Infra/External 区域。
- 如果图与代码不一致，以代码为准并立即修正文档。
