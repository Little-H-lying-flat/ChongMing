# 重明 (ChongMing)

重明是一个 AI 原生自动化质量工程平台，用一套前后端系统把需求解析、测试用例管理、UI/API 执行、性能压测、视觉回归、缺陷分析和模型治理串起来。当前代码采用前后端分离架构：前端是 Next.js 应用，后端是 FastAPI API 网关，异步执行依赖 Celery，核心测试能力下沉到 Services 和 Engines。

## 技术栈

| 层级 | 技术/目录 | 说明 |
|---|---|---|
| 前端 | `frontend/src` | Next.js 16、React 19、TypeScript、Tailwind CSS、TanStack Query |
| API 网关 | `backend/app/main.py`、`backend/app/api/v1` | FastAPI，统一挂载 `/api/v1` |
| 业务服务 | `backend/app/services` | 用例、执行、环境、数据工厂、Neural Design、Phoenix、Smart Ops 等服务 |
| 执行引擎 | `backend/app/engines` | Dispatcher、Right Pupil、Left Pupil、Turbo、Vision |
| 异步任务 | `backend/app/worker.py`、`backend/app/tasks` | Celery worker、beat、任务队列和进度状态 |
| 数据层 | `backend/app/models`、`backend/app/schemas` | SQLAlchemy 模型与 Pydantic 契约 |
| 部署 | `deploy/docker-compose.yml` | API、前端、Worker、PostgreSQL、Redis、ChromaDB、Milvus、OmniParser、Locust、监控 |

## 项目结构

```text
ChongMing/
├── backend/                 # FastAPI 后端、Celery 任务、测试执行引擎
│   ├── app/api/v1/          # API 路由和端点
│   ├── app/core/            # 配置、数据库、日志、AI 客户端、认证等基础设施
│   ├── app/services/        # 业务服务层
│   ├── app/engines/         # UI/API/性能/视觉等执行引擎
│   ├── app/tasks/           # Celery 任务
│   ├── app/models/          # SQLAlchemy 模型
│   └── app/schemas/         # API 与执行 IR 数据结构
├── frontend/                # Next.js 前端
│   └── src/app/             # App Router 页面
├── deploy/                  # Compose、Kubernetes、Nginx、Prometheus、OpenAPI
├── docs/                    # 架构图、设计分册、问题分册、接口/测试文档
├── scripts/                 # 本地校验、演示、健康检查脚本
└── tests/                   # 集成/手工测试
```

## 总体架构

```mermaid
flowchart LR
    User[用户/测试工程师] --> FE[Frontend Next.js]

    subgraph Frontend[前端页面与服务]
        FE --> Pages[App Routes]
        Pages --> FEServices[src/services]
    end

    subgraph API[FastAPI API Gateway]
        Router[/api/v1 router]
        Endpoints[health design executions visual-ui api-engine turbo phoenix smart-ops dashboard]
        Router --> Endpoints
    end

    subgraph Services[业务服务层]
        TestCase[TestCaseService]
        Execution[ExecutionService]
        Env[EnvironmentManager]
        Design[Neural Design Service]
        Visual[VisualUIService]
        Phoenix[Phoenix Service]
        SmartOps[Smart Ops Services]
        DataFactory[Data Factory]
    end

    subgraph Async[异步任务层]
        Celery[Celery App]
        ExecTask[execute_test_cases]
        DesignTask[analyze_requirement_task]
        PhoenixTask[phoenix tasks]
        Scheduled[scheduled tasks]
    end

    subgraph Engines[执行与智能引擎]
        Dispatcher[Dispatcher]
        Right[RightPupilEngine UI]
        Left[LeftPupilEngine API]
        Vision[Vision OmniClient SmartWaiter]
        Turbo[TurboEngine Locust]
        AI[AI Client Manager]
    end

    subgraph Infra[基础设施/外部系统]
        DB[(PostgreSQL or SQLite)]
        Redis[(Redis / Broker)]
        Chroma[(ChromaDB)]
        Milvus[(Milvus)]
        Omni[OmniParser]
        Locust[Locust]
        FS[(screenshots reports traces)]
        Target[被测 Web/API]
        LLM[Qwen/Gemini compatible LLM]
    end

    FEServices --> Router
    Endpoints --> TestCase
    Endpoints --> Execution
    Endpoints --> Env
    Endpoints --> Design
    Endpoints --> Visual
    Endpoints --> Phoenix
    Endpoints --> SmartOps
    Endpoints --> DataFactory
    Endpoints --> Celery
    Endpoints --> Turbo

    Celery --> ExecTask
    Celery --> DesignTask
    Celery --> PhoenixTask
    Celery --> Scheduled
    ExecTask --> Execution
    ExecTask --> Env
    ExecTask --> Dispatcher
    Dispatcher --> Right
    Dispatcher --> Left
    Right --> Vision
    Vision --> Omni
    Left --> Target
    Right --> Target
    Turbo --> Locust

    TestCase --> DB
    Execution --> DB
    Execution --> FS
    Env --> DB
    Design --> AI
    Design --> Chroma
    Phoenix --> AI
    SmartOps --> AI
    SmartOps --> Milvus
    DataFactory --> DB
    Celery --> Redis
    AI --> LLM
```

## 模块总览

### Neural Design / 需求解析

- 前端入口：`frontend/src/app/design/page.tsx`
- 后端入口：`backend/app/api/v1/endpoints/design.py`
- 服务层：`backend/app/services/neural_design/`
- 异步任务：`backend/app/tasks/design_tasks.py`
- 作用：解析 PRD、文档或自然语言需求，生成测试场景，并可导入 Visual UI 或执行链路。

### Test Case / 用例管理

- 后端入口：`backend/app/api/v1/endpoints/test_cases.py`
- 服务层：`backend/app/services/test_case_service.py`
- 模型：`backend/app/models/test_case.py`
- 作用：持久化 UI/API/HYBRID 测试用例，作为执行、压测和回归的输入。

### Execution Dispatcher / 执行调度

- 前端入口：`frontend/src/app/executions/page.tsx`
- 后端入口：`backend/app/api/v1/endpoints/executions.py`
- 服务层：`backend/app/services/execution_service.py`
- 异步任务：`backend/app/tasks/execution_tasks.py`
- 引擎入口：`backend/app/engines/dispatcher.py`
- 作用：创建执行记录，调度 Celery 或本地后台任务，按用例类型分发到 UI/API 引擎并写回结果。

### Right Pupil / 视觉 UI 自动化

- 前端入口：`frontend/src/app/visual-ui/page.tsx`、`frontend/src/app/visual-ui/scenario/[id]/page.tsx`
- 后端入口：`backend/app/api/v1/endpoints/visual_ui.py`
- 服务层：`backend/app/services/visual_ui_service.py`
- 引擎：`backend/app/engines/right_pupil/`、`backend/app/engines/vision/`
- 外部依赖：OmniParser、Playwright、被测 Web 页面。
- 作用：通过视觉识别和自然语言步骤执行 UI 自动化。

### Left Pupil / API 自动化

- 前端入口：`frontend/src/app/api-auto/page.tsx`
- 后端入口：`backend/app/api/v1/endpoints/api_engine.py`、`backend/app/api/v1/endpoints/left_pupil.py`
- 服务层：`backend/app/services/left_pupil/`
- 引擎：`backend/app/engines/left_pupil/`
- 作用：解析 API 规格、规划依赖、执行请求、断言响应、提取变量。

### Turbo / 性能压测

- 前端入口：`frontend/src/app/performance/page.tsx`、`frontend/src/app/turbo/page.tsx`
- 后端入口：`backend/app/api/v1/endpoints/turbo.py`
- 引擎：`backend/app/engines/turbo/`
- 外部依赖：Locust。
- 作用：把 API 用例转换为压测配置，生成数据和 Locust 脚本，启动/停止压测并查询实时指标。

### Phoenix / 脚本固化与回归治理

- 前端入口：`frontend/src/app/phoenix/page.tsx`
- 后端入口：`backend/app/api/v1/endpoints/phoenix.py`
- 服务层：`backend/app/services/phoenix/`
- 任务：`backend/app/tasks/phoenix_tasks.py`
- 作用：将执行轨迹编译为脚本，管理回归基线、视觉/API 对比和 Git 集成。

### Smart Ops / 智能运维与模型治理

- 前端入口：`frontend/src/app/smart-ops/page.tsx`、`frontend/src/app/model-config/page.tsx`
- 后端入口：`backend/app/api/v1/endpoints/smart_ops.py`
- 服务层：`backend/app/services/smart_ops/`
- 外部依赖：LLM、Milvus。
- 作用：模型配置、Token 指标、缺陷根因分析、相似缺陷检索。

### Environment & Data Factory / 环境和数据

- 后端入口：`backend/app/api/v1/endpoints/environments.py`、`backend/app/api/v1/endpoints/data_factory.py`
- 服务层：`backend/app/services/environment_manager.py`、`backend/app/services/data_factory.py`
- 作用：维护环境变量、base URL、加密变量和测试数据模板/数据池。

## 核心调用链

### 1. 需求到用例

```text
/design 页面
  -> POST /api/v1/design/analyze 或上传文档
  -> DesignService / analyze_requirement_task
  -> AI Client + RAG Retriever
  -> 生成 scenarios / refined test cases
  -> 可导入 Visual UI 或作为 dynamic_payload 提交执行
```

### 2. 用例执行到结果

```text
/executions 页面选择 tc_ids
  -> POST /api/v1/executions
  -> ExecutionService.create_execution 写入 PENDING
  -> 有 Celery worker 时 execute_test_cases.delay，否则 FastAPI BackgroundTasks 本地执行
  -> execute_test_cases 读取用例和环境变量
  -> Dispatcher 按 UI/API/HYBRID 分支执行
  -> RightPupilEngine 调 OmniParser/Playwright，LeftPupilEngine 调目标 API
  -> ExecutionService.create_step_result 写入步骤结果和截图引用
  -> ExecutionService.update_execution_status 写入最终状态
  -> 前端轮询 GET /api/v1/executions/{id} 和 GET /api/v1/executions/{id}/result
```

### 3. 性能压测

```text
/performance 或 /turbo 页面
  -> POST /api/v1/turbo/run
  -> TurboEngine 合成数据、编译 locustfile、启动 Locust
  -> GET /api/v1/turbo/stats/{test_id} 查询 RPS、失败率、P95 等指标
  -> POST /api/v1/turbo/stop/{test_id} 停止压测
```

### 4. 缺陷分析和模型治理

```text
/smart-ops 或 /model-config 页面
  -> /api/v1/smart-ops/*
  -> AIConfigService / DefectManager / VectorStore
  -> LLM 生成根因和修复建议
  -> Milvus 检索相似缺陷
  -> 前端展示历史缺陷、模型配置和 Token 指标
```

## 本地启动

### 后端

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

如需异步任务：

```bash
cd backend
celery -A app.worker:celery worker -l INFO -Q high,normal,low,execution,design,phoenix,turbo
celery -A app.worker:celery beat -l INFO
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

默认访问：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

前端默认调用 `NEXT_PUBLIC_API_URL`；未配置时使用 `http://127.0.0.1:8000/api/v1`。

### Docker Compose

```bash
cd deploy
cp .env.example .env
# 编辑 .env，填写 QWEN_API_KEY、数据库密码等
docker-compose up -d
```

Compose 会启动 API、前端、多个 worker、PostgreSQL、Redis、ChromaDB、Milvus、OmniParser、Locust、Prometheus、Grafana 和 Nginx。详见 `deploy/README.md`。

## 常用校验

```bash
python scripts/check_utf8.py
python scripts/check_mermaid_diagrams.py
pytest backend/tests tests
```

前端：

```bash
cd frontend
npm run lint
npm run build
```

## 文档索引

- `backend/README.md`：后端模块、API、任务和执行链路。
- `frontend/README.md`：前端页面、服务层和调用方式。
- `deploy/README.md`：容器、端口、队列和部署拓扑。
- `docs/diagrams/README.md`：架构图和 Mermaid 调用链维护说明。
- `docs/designs/README.md`：详细设计分册索引。
- `docs/issues/README.md`：模块问题和技术债分册索引。
- `docs/API_REFERENCE.md`：接口参考。
- `docs/接口对接文档.md`、`docs/测试策略文档.md`、`docs/开发规范文档.md`：协作、测试和开发规范。
