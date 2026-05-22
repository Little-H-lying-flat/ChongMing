# ChongMing API Reference

## 1. 平台概述 (Platform Overview)

ChongMing (重明) 是一个下一代智能测试平台，核心能力包括：
- **Neural Design**: 基于 LLM 的需求分析与用例生成。
- **Right Pupil**: 视觉驱动的 UI 自动化引擎 (Visual Grounding)。
- **Left Pupil**: 协议驱动的 API 自动化引擎 (API-IR)。
- **API Asset**: OpenAPI/Swagger 接口资产库，可生成 API Case IR v2 步骤。
- **Turbo Engine**: 高并发性能压测引擎。
- **Smart Ops**: AI 模型治理与成本控制。

### 1.1 基础信息
- **Base URL**: `http://<server-ip>:8000/api/v1`
- **Current Version**: `v1.0.0`

### 1.2 鉴权方式 (Authentication)
目前平台主要用于内网环境。
- **UI Dashboard**: 无需鉴权。
- **API Call**: 部分管理接口可能需要 `Authorization: Bearer <token>` (如需)。

---

## 2. 核心业务流 API (Core Business Flows)

### Flow 1: Neural Design (需求解析)

#### 1.1 需求分析 (Analyze PRD)
**描述**: 接收自然语言需求或 PRD 文档，使用 Agent 进行语义分析，生成测试场景列表。

- **Method**: `POST`
- **Path**: `/design/analyze`

**Request Body (JSON)**:
```json
{
  "project_id": "proj_001",
  "requirement_text": "用户登录功能：用户输入用户名和密码，点击登录按钮。若验证通过则跳转首页，否则提示错误。",
  "context": "相关接口文档链接..."
}
```

**Response (200 OK)**:
```json
[
  {
    "scenario_id": "SCN_01",
    "description": "登录成功流程",
    "steps": ["输入正确用户名", "输入正确密码", "点击登录"],
    "priority": "P0"
  },
  {
    "scenario_id": "SCN_02",
    "description": "登录失败-密码错误",
    "steps": ["输入正确用户名", "输入错误密码", "点击登录"],
    "priority": "P1"
  }
]
```

#### 1.2 生成测试用例 (Generate Test Case)
**描述**: 根据测试场景生成详细的自动化测试用例 (API-IR 格式)。

- **Method**: `POST`
- **Path**: `/design/generate`

**Request Body (JSON)**:
```json
{
  "project_id": "proj_001",
  "scenario": {
    "scenario_id": "SCN_01",
    "description": "登录成功流程",
    "steps": ["输入正确用户名", "输入正确密码", "点击登录"]
  }
}
```

**Response (200 OK)**:
```json
{
  "id": "TC_LOGIN_SUCCESS",
  "name": "登录成功测试",
  "description": "验证用户能否成功登录",
  "steps": [
    {
      "id": "STEP_01",
      "name": "调用登录接口",
      "request": {
        "method": "POST",
        "url": "https://api.example.com/login",
        "body": {"username": "admin", "password": "***"}
      },
      "assertion": {
        "status_code": 200,
        "json_assertions": {"$.success": true}
      }
    }
  ]
}
```

---

### Flow 2: Visual UI (右瞳引擎)

#### 2.1 提交异步 UI 任务 (Run UI Task Async)
**描述**: 将自然语言驱动的 UI 自动化任务投递到 Worker 队列，支持高并发。

- **Method**: `POST`
- **Path**: `/executions/ui/run/async`

**Request Body (JSON)**:
```json
{
  "prompt": "打开百度首页，搜索 'ChongMing Test Platform'，并点击第一条结果。",
  "url": "https://www.baidu.com"
}
```

**Response (202 Accepted)**:
```json
{
  "task_id": "31e3ff94-a01e-445b-9cd3-6e83f92a1160",
  "status": "pending",
  "dashboard_url": "/tasks/31e3ff94-a01e-445b-9cd3-6e83f92a1160/progress"
}
```

---

### Flow 3: Execution Dispatcher (任务调度)

#### 3.1 启动测试执行 (Start Execution)
**描述**: 提交并调度一批测试用例 (TC-IR)，返回执行活动 ID。

- **Method**: `POST`
- **Path**: `/executions`

**Request Body (JSON)**:
```json
{
  "tc_ids": ["TC_001", "TC_002"],
  "mode": "normal",
  "parallel": true,
  "max_workers": 5,
  "env": "staging"
}
```

**Response (202 Accepted)**:
```json
{
  "execution_id": "exec_550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "total_cases": 2,
  "dashboard_url": "/executions/exec_550e8400-e29b-41d4-a716-446655440000"
}
```

#### 3.2 获取执行状态 (Get Status)
**描述**: 实时轮询执行进度与状态。

- **Method**: `GET`
- **Path**: `/executions/{execution_id}`

**Response (200 OK)**:
```json
{
  "execution_id": "exec_550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 50.0,
  "passed": 1,
  "failed": 0,
  "start_time": "2023-10-27T10:00:00Z",
  "elapsed_seconds": 15.5
}
```

---

### Flow 4: Left Pupil (API Automation)

#### 4.1 执行单步 (Execute Step)
**描述**: 执行单个 API-IR 步骤，支持变量注入与提取。

- **Method**: `POST`
- **Path**: `/left-pupil/execute`

**Request Body (JSON)**:
```json
{
  "base_url": "https://api.example.com",
  "context": {"token": "eyJhbGci..."},
  "step": {
    "id": "STEP_USER_INFO",
    "name": "Get User Info",
    "request": {
      "method": "GET",
      "url": "/users/me",
      "headers": {"Authorization": "Bearer ${token}"}
    },
    "extraction": {
      "user_id": "$.data.id"
    },
    "assertion": {
      "status_code": 200,
      "json_assertions": {"$.data.role": "admin"}
    }
  }
}
```

**Response (200 OK)**:
```json
{
  "step_id": "STEP_USER_INFO",
  "status": "passed",
  "status_code": 200,
  "duration_ms": 120.5,
  "extracted_values": {"user_id": 1001},
  "assertion_passed": true
}
```

#### 4.2 执行链路 (Execute Chain)
**描述**: 顺序执行一组 API 步骤，自动传递上下文。

- **Method**: `POST`
- **Path**: `/left-pupil/execute-chain`

**Request Body (JSON)**:
```json
{
  "base_url": "https://api.example.com",
  "steps": [
    { "id": "STEP_1", "request": { "method": "POST", "url": "/login" }, "extraction": {"token": "$.token"} },
    { "id": "STEP_2", "request": { "method": "GET", "url": "/profile", "headers": {"Authorization": "${token}"} } }
  ]
}
```

---

### Flow 5: API Asset (接口资产库)

#### 5.1 导入 OpenAPI / Swagger (Import OpenAPI)
**描述**: 从 inline OpenAPI/Swagger JSON 或远程 URL 导入接口资产；同一 `source_name + method + path` 重复导入时更新现有资产。

- **Method**: `POST`
- **Path**: `/api-assets/import-openapi`

**Request Body (JSON)**:
```json
{
  "source_name": "catalog-service",
  "content": {
    "openapi": "3.0.0",
    "info": {"title": "Catalog API", "version": "2026.1"},
    "servers": [{"url": "https://catalog.example.test"}],
    "paths": {
      "/products": {
        "get": {
          "summary": "List products",
          "operationId": "listProducts",
          "tags": ["catalog"],
          "parameters": [
            {"name": "q", "in": "query", "schema": {"type": "string"}}
          ],
          "responses": {"200": {"description": "OK"}}
        }
      }
    }
  }
}
```

也可以只传 `url`：
```json
{
  "source_name": "catalog-service",
  "url": "https://example.test/openapi.json"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "source_name": "catalog-service",
  "source_type": "openapi_content",
  "spec_title": "Catalog API",
  "spec_version": "2026.1",
  "base_url": "https://catalog.example.test",
  "parsed_count": 1,
  "created_count": 1,
  "updated_count": 0,
  "skipped_count": 0,
  "asset_ids": ["API-ASSET-0E334835"]
}
```

#### 5.2 查询接口资产 (List Assets)
**描述**: 分页查询接口资产，支持关键词、HTTP 方法、标签、来源和废弃状态过滤。

- **Method**: `GET`
- **Path**: `/api-assets`

**Query Parameters**:
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `page` | integer | `1` | 页码 |
| `page_size` | integer | `20` | 每页数量，最大 200 |
| `keyword` | string | - | 搜索 method/path/name/summary/description/operation_id/search_text |
| `method` | string | - | HTTP 方法，如 `GET` / `POST` |
| `tag` | string | - | 标签关键词 |
| `source_name` | string | - | 来源名称 |
| `deprecated` | boolean | - | 是否只查废弃资产 |

**Response (200 OK)**:
```json
{
  "items": [
    {
      "id": "API-ASSET-0E334835",
      "asset_key": "catalog-service:GET /products",
      "source_name": "catalog-service",
      "source_type": "openapi_content",
      "base_url": "https://catalog.example.test",
      "name": "List products",
      "method": "GET",
      "path": "/products",
      "summary": "List products",
      "operation_id": "listProducts",
      "tags": ["catalog"],
      "parameters": [
        {"name": "q", "location": "query", "required": false, "schema_type": "string"}
      ],
      "request_body": null,
      "responses": {"200": {"status_code": "200", "description": "OK", "schema": {}}},
      "deprecated": false
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

#### 5.3 手工维护接口资产 (Create / Update / Delete Asset)
**描述**: 手工创建、查看、更新或删除接口资产。手工创建时同一 `source_name + method + path` 已存在会返回 409。

- **Create**: `POST /api-assets`
- **Detail**: `GET /api-assets/{asset_id}`
- **Update**: `PUT /api-assets/{asset_id}`
- **Delete**: `DELETE /api-assets/{asset_id}`

**Create Request Body (JSON)**:
```json
{
  "source_name": "manual-suite",
  "method": "POST",
  "path": "/orders",
  "summary": "Create order",
  "tags": ["orders"],
  "request_body": {
    "content_type": "application/json",
    "schema": {"type": "object"}
  },
  "responses": {
    "201": {"description": "Created"}
  }
}
```

**Create Response (201 Created)**:
```json
{
  "id": "API-ASSET-12345678",
  "asset_key": "manual-suite:POST /orders",
  "source_name": "manual-suite",
  "source_type": "manual",
  "name": "Create order",
  "method": "POST",
  "path": "/orders",
  "summary": "Create order",
  "tags": ["orders"],
  "deprecated": false
}
```

#### 5.4 生成 API Case IR v2 Step (Generate API IR Step)
**描述**: 将接口资产转换为可放入 `TestCase.steps` 或动态执行 payload 的标准 API Case IR v2 步骤。

- **Method**: `GET`
- **Path**: `/api-assets/{asset_id}/api-ir-step`

**Response (200 OK)**:
```json
{
  "step": {
    "id": "STEP_API-ASSET-0E334835",
    "name": "List products",
    "description": "List products",
    "step_type": "API",
    "protocol": "API-IR",
    "version": "2.0",
    "request": {
      "method": "GET",
      "url": "/products",
      "path": "/products",
      "headers": {},
      "query_params": {"q": ""},
      "path_params": {},
      "body": null,
      "timeout_ms": 30000,
      "content_type": "application/json",
      "base_url": "https://catalog.example.test"
    },
    "assertion": {
      "status_code": 200,
      "json_assertions": {}
    },
    "extraction": {},
    "metadata": {
      "source_type": "api_asset",
      "source_id": "API-ASSET-0E334835",
      "asset_key": "catalog-service:GET /products",
      "source_name": "catalog-service",
      "operation_id": "listProducts",
      "tags": ["catalog"]
    },
    "method": "GET",
    "url": "/products",
    "query_params": {"q": ""},
    "expected_status_code": 200,
    "json_assertions": {},
    "extract": {},
    "assertions": [{"type": "status_code", "expected": 200}]
  }
}
```

---

### Flow 6: Turbo Engine (性能压测)

#### 6.1 启动压测 (Start Load Test)
**描述**: 启动基于 Locust 的高性能压测任务。

- **Method**: `POST`
- **Path**: `/turbo/run`

**Request Body (JSON)**:
```json
{
  "target_host": "https://target-api.com",
  "users": 1000,
  "spawn_rate": 50,
  "run_time": "5m",
  "spawn_count": 1000,
  "api_ir_chain": [
     { "method": "GET", "url": "/benchmark", "weight": 1 }
  ]
}
```

**Response (200 OK)**:
```json
{
  "test_id": "test_c4d29a",
  "status": "started"
}
```

#### 6.2 获取压测统计 (Get Stats)
**描述**: 获取实时压测指标 (RPS, Latency)。

- **Method**: `GET`
- **Path**: `/turbo/stats/{test_id}`

**Response (200 OK)**:
```json
{
  "test_id": "test_c4d29a",
  "state": "running",
  "users": 500,
  "current_rps": 1250.5,
  "fail_ratio": 0.001,
  "p95_response_time": 45.2
}
```

---

### Flow 7: Smart Ops (模型治理)

#### 7.1 获取模块配置 (Get Module Configs)
**描述**: 获取各业务模块 (Planning, Coding) 当前绑定的模型配置。

- **Method**: `GET`
- **Path**: `/smart-ops/config`

**Response (200 OK)**:
```json
[
  {
    "module": "planning",
    "model_id": "gpt-4-turbo",
    "provider": "openai",
    "temperature": 0.7
  },
  {
    "module": "coding",
    "model_id": "claude-3-opus",
    "provider": "anthropic",
    "max_tokens": 4096
  }
]
```

#### 7.2 更新模型映射 (Update Config)
**描述**: 动态切换业务模块使用的 AI 模型。

- **Method**: `POST`
- **Path**: `/smart-ops/config`

**Request Body (JSON)**:
```json
{
  "module": "planning",
  "model_id": "gpt-3.5-turbo",
  "temperature": 0.5
}
```

---

## 3. 状态码字典 (Status Codes)

### HTTP Status Codes
| Code | Description | Meaning |
| :--- | :--- | :--- |
| **200** | OK | 请求成功 |
| **202** | Accepted | 异步任务已接受，正在排队 |
| **400** | Bad Request | 请求参数错误或校验失败 |
| **401** | Unauthorized | 未鉴权或 Token 失效 |
| **404** | Not Found | 资源不存在 (如无效的 test_id) |
| **409** | Conflict | 资源冲突 (如任务已在运行) |
| **500** | Internal Server Error | 服务器内部错误 |

### 业务状态 (Execution Status)
- **pending**: 等待被 Worker 消费。
- **running**: 正在执行中。
- **passed**: 执行完成且全部校验通过。
- **failed**: 执行完成但存在断言失败或错误。
- **error**: 执行过程中发生系统级异常。
