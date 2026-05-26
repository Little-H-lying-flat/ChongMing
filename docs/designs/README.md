# 详细设计分册索引

`docs/designs/` 保存重明平台的模块级详细设计材料。这里的文档用于解释模块边界、设计意图、关键流程和治理规则；代码事实以 `backend/`、`frontend/`、`deploy/` 的当前实现为准。

## 推荐阅读顺序

1. 先读仓库根目录 [`README.md`](../../README.md)，了解整体架构和核心调用链。
2. 再读 [`docs/diagrams/README.md`](../diagrams/README.md)，查看当前 Mermaid 架构图和时序图。
3. 按模块阅读本目录的详细设计文档。
4. 如需看问题和技术债，进入 [`docs/issues/README.md`](../issues/README.md)。

## 当前代码模块映射

| 领域 | 主要代码路径 | 设计分册 |
|---|---|---|
| API 网关层 | `backend/app/main.py`、`backend/app/api/v1/router.py`、`backend/app/api/v1/endpoints/` | `重明_详细设计说明书_API网关层.txt` |
| Neural Design | `backend/app/api/v1/endpoints/design.py`、`backend/app/services/neural_design/`、`backend/app/tasks/design_tasks.py` | `重明_详细设计说明书_神经设计层.txt` |
| Midscene / Visual UI | `backend/app/services/midscene_adapter.py`、`backend/app/services/visual_ui_service.py`、`backend/app/api/v1/endpoints/visual_ui.py` | `重明_详细设计说明书_右瞳引擎.txt`（已退役历史方案）、`重明_详细设计说明书_智能等待机制.txt`（已退役历史方案） |
| Left Pupil / API | `backend/app/engines/left_pupil/`、`backend/app/services/left_pupil/`、`backend/app/api/v1/endpoints/api_engine.py`、`backend/app/api/v1/endpoints/left_pupil.py` | `重明_详细设计说明书_左瞳引擎.txt` |
| 双模态调度 | `backend/app/engines/dispatcher.py`、`backend/app/tasks/execution_tasks.py`、`backend/app/services/execution_service.py` | `重明_详细设计说明书_双模态执行.txt`、`重明_详细设计说明书_Celery任务调度.txt` |
| Turbo 性能压测 | `backend/app/api/v1/endpoints/turbo.py`、`backend/app/engines/turbo/`、`deploy/locust/` | `重明_详细设计说明书_涡轮引擎.txt` |
| Phoenix | `backend/app/api/v1/endpoints/phoenix.py`、`backend/app/services/phoenix/`、`backend/app/tasks/phoenix_tasks.py` | `重明_详细设计说明书_凤凰涅槃层.txt` |
| Smart Ops / 缺陷分析 | `backend/app/api/v1/endpoints/smart_ops.py`、`backend/app/services/smart_ops/` | `重明_详细设计说明书_缺陷分析智能体.txt`、`重明_详细设计说明书_自愈中心模块.txt` |
| VRT 视觉回归 | `backend/app/services/phoenix/regression/visual_comparator.py`、`backend/app/engines/vision/` | `重明_详细设计说明书_VRT视觉回归测试.txt` |
| 环境管理 | `backend/app/api/v1/endpoints/environments.py`、`backend/app/services/environment_manager.py` | `重明_详细设计说明书_环境管理模块.txt` |
| 数据工厂 | `backend/app/api/v1/endpoints/data_factory.py`、`backend/app/services/data_factory.py`、`backend/app/services/data_pool.py`、`backend/app/services/data_template.py` | `重明_详细设计说明书_数据工厂模块.txt` |
| 前端层 | `frontend/src/app/`、`frontend/src/components/`、`frontend/src/services/` | `重明_详细设计说明书_前端层.txt` |
| 报告和可视化 | `frontend/src/app/executions/`、`frontend/src/components/ui/execution-drawer.tsx`、`backend/app/services/execution_service.py` | `重明_详细设计说明书_报告可视化模块.txt` |
| UI + API 智能扫描 | `frontend/src/app/`、`frontend/src/services/`、`backend/app/api/v1/endpoints/`、`backend/app/engines/dispatcher.py` | `UI_API智能扫描模式计划书.md` |

## 分册清单

| 文件 | 说明 |
|---|---|
| `重明架构白皮书.txt` | 全局分层、能力边界和系统视角 |
| `重明技术规格书.txt` | 平台级规格、能力清单、约束 |
| `重明_详细设计说明书_API网关层.txt` | FastAPI 入口、路由聚合、接口治理 |
| `重明_详细设计说明书_神经设计层.txt` | PRD/需求解析、场景生成、评审和编排 |
| `重明_详细设计说明书_右瞳引擎.txt` | 已退役历史方案：RightPupil/OmniParser 旧 UI 自动化设计，当前实现以 Midscene 为准 |
| `重明_详细设计说明书_左瞳引擎.txt` | API 自动化、依赖规划、断言和变量提取 |
| `重明_详细设计说明书_双模态执行.txt` | UI/API/HYBRID 执行分支和 Dispatcher 策略 |
| `重明_详细设计说明书_涡轮引擎.txt` | 性能压测脚本生成、数据合成和 Locust 执行 |
| `重明_详细设计说明书_凤凰涅槃层.txt` | 执行轨迹编译、脚本固化、回归治理 |
| `重明_详细设计说明书_缺陷分析智能体.txt` | 根因分析、相似缺陷检索、修复建议 |
| `重明_详细设计说明书_自愈中心模块.txt` | 自愈流程、策略边界和失败兜底 |
| `重明_详细设计说明书_智能等待机制.txt` | 页面稳定检测、视觉等待和误判控制 |
| `重明_详细设计说明书_VRT视觉回归测试.txt` | 视觉回归比对、动态噪声处理 |
| `重明_详细设计说明书_Celery任务调度.txt` | 队列、worker、进度跟踪和定时任务 |
| `重明_详细设计说明书_环境管理模块.txt` | 环境变量、base URL、加密变量 |
| `重明_详细设计说明书_数据工厂模块.txt` | 测试数据模板、数据池、合成数据 |
| `重明_详细设计说明书_前端层.txt` | 页面模块、服务层和后端接口映射 |
| `重明_详细设计说明书_报告可视化模块.txt` | 执行结果展示、报告和看板 |
| `测试用例管理模块实施说明.md` | 测试用例管理实现说明 |
| `UI_API智能扫描模式计划书.md` | Scope-based UI + API 智能扫描模式的产品目标、边界、验收和阶段路线 |
| `UI_API智能扫描_Phase0样例与模板.md` | Phase 0 的业务样例、用户输入模板、禁止动作词表和报告样例 |
| `UI_API智能扫描_Phase0计划质量评审.md` | 10 个样例的计划生成质量评审、问题归因和进入 Phase 1 前置条件 |
| `UI_API智能扫描_Phase1页面信息结构.md` | Phase 1 的 Campaign 创建页、计划预览页和执行前确认页字段结构 |
| `UI_API智能扫描_Phase1接口与映射规则.md` | Phase 1 的 API 候选匹配、资产草稿映射和后端接口草案 |
| `UI_API智能扫描_Phase1低保真布局.md` | Phase 1 的 Campaign 创建页、计划预览页和执行前确认页低保真布局 |
| `UI_API智能扫描_Phase1后端表与接口设计.md` | Phase 1 的 Campaign draft 表结构、后端 service 边界和接口处理流程 |

## 维护规则

- 设计分册说明“为什么这样设计”，README 和代码说明“当前实际是什么”。
- 新增、删除、重命名模块时，同步更新本索引、根 README 和对应 Mermaid 图。
- 如果分册描述与代码冲突，优先核对当前代码，再修正文档。
- 变更调用链时，同步更新 `docs/diagrams/*.mmd`，并运行 `python scripts/check_mermaid_diagrams.py`。
