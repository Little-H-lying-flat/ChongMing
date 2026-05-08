# 模块问题与技术债分册索引

`docs/issues/` 保存重明平台的模块级问题、技术债、测试计划和治理任务。这里用于跟踪“哪些模块还有风险”和“下一步怎么收敛”，不是运行时状态记录。

## 使用方式

1. 先在根目录 `README.md` 和 `docs/diagrams/` 确认模块边界和调用链。
2. 再进入对应 issue 分册查看问题列表、优先级、验收指标和治理建议。
3. 关闭或新增问题时，同步更新本索引和相关设计/架构图。

## 模块到代码路径映射

| 模块 | 主要代码路径 | Issue 分册 |
|---|---|---|
| 全局任务池 | 全仓库 | `00_任务总览.md` |
| Neural Design | `backend/app/api/v1/endpoints/design.py`、`backend/app/services/neural_design/`、`backend/app/tasks/design_tasks.py` | `01_神经设计层_issues.md` |
| Right Pupil / UI | `backend/app/engines/right_pupil/`、`backend/app/engines/vision/`、`frontend/src/app/visual-ui/` | `02_右瞳引擎_issues.md` |
| Left Pupil / API | `backend/app/engines/left_pupil/`、`backend/app/services/left_pupil/`、`frontend/src/app/api-auto/` | `03_左瞳引擎_issues.md` |
| Turbo | `backend/app/api/v1/endpoints/turbo.py`、`backend/app/engines/turbo/`、`deploy/locust/` | `04_涡轮引擎_issues.md` |
| Phoenix | `backend/app/api/v1/endpoints/phoenix.py`、`backend/app/services/phoenix/`、`backend/app/tasks/phoenix_tasks.py` | `05_凤凰涅槃层_issues.md` |
| Smart Ops / 缺陷分析 | `backend/app/api/v1/endpoints/smart_ops.py`、`backend/app/services/smart_ops/` | `06_缺陷分析智能体_issues.md` |
| 自愈中心 | `backend/app/engines/right_pupil/agents/healer.py`、`backend/app/engines/left_pupil/agents/api_healer.py` | `07_自愈中心_issues.md` |
| 智能等待 | `backend/app/engines/vision/smart_waiter.py` | `08_智能等待机制_issues.md` |
| VRT 视觉回归 | `backend/app/services/phoenix/regression/visual_comparator.py` | `09_VRT视觉回归_issues.md` |
| Celery 任务调度 | `backend/app/worker.py`、`backend/app/tasks/`、`backend/app/api/v1/endpoints/tasks.py` | `10_Celery任务调度_issues.md` |
| LangGraph/编排 | `backend/app/services/neural_design/graph.py`、`backend/app/engines/*/graph.py` | `11_LangGraph编排_issues.md` |
| 前端层 | `frontend/src/app/`、`frontend/src/components/`、`frontend/src/services/` | `12_前端层_issues.md` |
| API 网关层 | `backend/app/main.py`、`backend/app/api/v1/router.py`、`backend/app/api/v1/endpoints/` | `13_API网关层_issues.md` |
| 报告/数据/环境 | `backend/app/services/execution_service.py`、`backend/app/services/data_*`、`backend/app/services/environment_manager.py` | `14_报告_数据_环境_issues.md` |
| 缓存/记忆 | `backend/app/core/memory_base.py`、`backend/app/services/left_pupil/context_memory.py`、`backend/app/core/chroma_client.py` | `15_神经缓存层_issues.md` |

## 分册清单

| 文件 | 说明 |
|---|---|
| `00_任务总览.md` | 全局任务池和阶段目标 |
| `01_神经设计层_issues.md` | 需求解析、场景生成、评审链路问题 |
| `02_右瞳引擎_issues.md` | UI 自动化稳定性、视觉定位、自愈问题 |
| `03_左瞳引擎_issues.md` | API 链路、依赖规划、断言、变量提取问题 |
| `04_涡轮引擎_issues.md` | 压测脚本、数据合成、实时统计问题 |
| `05_凤凰涅槃层_issues.md` | 轨迹编译、脚本固化、回归治理问题 |
| `06_缺陷分析智能体_issues.md` | 根因分析、相似缺陷检索、修复建议问题 |
| `07_自愈中心_issues.md` | UI/API 自愈策略、失败兜底和边界问题 |
| `08_智能等待机制_issues.md` | 页面稳定检测、等待条件、误判问题 |
| `09_VRT视觉回归_issues.md` | 视觉对比、动态噪声、误报控制问题 |
| `10_Celery任务调度_issues.md` | 队列、worker、任务进度和状态一致性问题 |
| `11_LangGraph编排_issues.md` | 图编排、可解释性、失败恢复问题 |
| `12_前端层_issues.md` | 页面交互、服务层契约、状态管理问题 |
| `13_API网关层_issues.md` | 路由治理、接口契约、错误语义问题 |
| `14_报告_数据_环境_issues.md` | 执行报告、测试数据、环境变量问题 |
| `15_神经缓存层_issues.md` | 缓存一致性、RAG/记忆层、检索质量问题 |
| `测试用例管理_测试计划.md` | 测试用例管理模块测试计划 |

## 优先级规则

| 优先级 | 含义 | 要求 |
|---|---|---|
| High | 阻断核心链路或存在高风险误判 | 必须有复现步骤、影响范围、验收指标 |
| Medium | 影响模块稳定性、体验或可维护性 | 应说明触发条件和推荐修复方向 |
| Low | 长期治理、体验优化、文档补齐 | 应有防回归或后续检查方式 |

## 维护规则

- 不把临时运行日志直接写入 issue 分册；运行状态以数据库、日志和 Git 历史为准。
- 每个 issue 应尽量包含：现象、影响、代码路径、复现方式、期望结果、验收标准。
- 修改 API 路径、队列名、服务边界或调用链时，同步更新 `docs/diagrams/` 和相关 README。
- 如果 issue 已被代码修复，不保留过期 workaround；改为记录最终行为和验证方式。
