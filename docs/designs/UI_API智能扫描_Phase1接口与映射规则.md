# UI + API 智能扫描 Phase 1 接口与映射规则

## 1. 文档定位

本文补充 Phase 1 进入实现前必须明确的三类规则：

1. API 候选来源与匹配展示规则。
2. AI plan 到 API / UI 资产草稿的映射规则。
3. Campaign draft、AI plan、人工确认和资产草稿的后端接口草案。

Phase 1 仍然不提供执行接口，不调用 Left Pupil / Right Pupil 执行测试。

## 2. API 候选来源标记

API candidate 必须明确来源。来源决定可信度、展示顺序、可否生成 API Case IR v2、以及 source_ref 如何保存。

| source | 名称 | 来源说明 | 默认可信度 | 是否可生成 step |
|---|---|---|---|---|
| `api_asset` | API Asset | 已导入或手工维护的接口资产 | 高 | 是 |
| `network_observed` | 浏览器 Network | UI 探索过程中真实观察到的请求 | 高 | 是，但需补断言 |
| `existing_test_case` | 已有 Test Case | 现有 API/UI/HYBRID 用例中的 API step | 中高 | 是 |
| `ai_inferred` | AI 推断 | AI 根据自然语言、页面文案或代码上下文推断 | 中低 | 默认只展示，需确认后生成 draft |

### 2.1 source_ref 结构

```json
{
  "source": "api_asset",
  "source_ref": {
    "asset_id": "ASSET_001",
    "asset_key": "user-service:POST:/api/users",
    "operation_id": "createUser",
    "source_name": "user-service-openapi"
  }
}
```

不同来源的 `source_ref`：

| source | source_ref 必填字段 |
|---|---|
| `api_asset` | `asset_id`、`asset_key`、`source_name`，有则带 `operation_id` |
| `network_observed` | `request_id`、`method`、`url`、`observed_at`、`page_url` |
| `existing_test_case` | `test_case_id`、`step_id`、`case_name` |
| `ai_inferred` | `inference_reason`、`matched_text`、`confidence` |

## 3. API 候选匹配排序规则

当多个接口匹配同一个自然语言步骤时，按评分排序。前端展示评分原因，不只展示最终排序。

### 3.1 排序优先级

| 排序项 | 权重 | 说明 |
|---|---:|---|
| 路径命中 allowed_paths | 30 | 不命中则必须降级为 out_of_scope |
| source 可信度 | 25 | API Asset / Network 高于 AI 推断 |
| method 与动作匹配 | 15 | “查询”优先 GET，“新建”优先 POST |
| operation_id / summary 语义匹配 | 15 | 和自然语言步骤语义越接近越高 |
| 现有用例复用 | 10 | 已稳定执行过的用例优先 |
| 风险更低 | 5 | 只读优先于写操作 |

### 3.2 source 可信度分

| source | 分值 |
|---|---:|
| `api_asset` | 1.0 |
| `network_observed` | 0.95 |
| `existing_test_case` | 0.85 |
| `ai_inferred` | 0.55 |

### 3.3 匹配结果展示字段

```json
{
  "candidate_id": "API_CANDIDATE_001",
  "natural_language_step": "新建用户",
  "method": "POST",
  "path": "/api/users",
  "source": "api_asset",
  "match_score": 0.91,
  "match_reasons": [
    "path 命中 /api/users",
    "operation_id=createUser 与新建用户语义匹配",
    "method=POST 符合新建动作"
  ],
  "policy": "confirmation_required"
}
```

## 4. 只能展示、不能生成 step 的接口

以下 API candidate 只能展示在计划中，不能生成 API Case IR v2 step：

| 场景 | 原因 | 展示策略 |
|---|---|---|
| 超出 allowed_domains | 越界访问 | 标记 `out_of_scope` |
| 超出 allowed_paths | 越界路径 | 标记 `out_of_scope` |
| source=`ai_inferred` 且 confidence < 0.7 | 可信度不足 | 仅展示推断原因 |
| policy=`forbidden` | 禁止动作 | 仅展示不执行原因 |
| 真实支付、真实扣款、提现、真实退款 | 资金风险 | 标记 `forbidden` |
| 权限变更、提权、角色分配 | 权限风险 | Phase 1 只生成计划 |
| 缺少 required path/query/body 参数 | 无法形成可执行请求 | 展示缺失参数 |
| 条件允许但条件未通过 | 条件不足 | 展示未满足条件 |

## 5. source_ref / metadata 保留到 API Case IR v2

从 API candidate 生成 API Case IR v2 draft 时，必须保留来源和风险元数据。

### 5.1 metadata 标准字段

```json
{
  "metadata": {
    "source_type": "scan_campaign",
    "campaign_id": "CMP_DRAFT_001",
    "plan_id": "PLAN_001",
    "candidate_id": "API_CANDIDATE_001",
    "candidate_source": "api_asset",
    "source_ref": {
      "asset_id": "ASSET_001",
      "asset_key": "user-service:POST:/api/users",
      "operation_id": "createUser",
      "source_name": "user-service-openapi"
    },
    "policy": "confirmation_required",
    "risk_level": "medium",
    "risk_reason": "会写入 test_user_* 测试数据",
    "conditions": [
      {"name": "环境非生产", "status": "passed", "detail": "staging"},
      {"name": "测试数据标识存在", "status": "passed", "detail": "test_user_*"}
    ],
    "execution_allowed_in_phase": false
  }
}
```

### 5.2 与 API Asset metadata 的关系

如果 candidate 来自 API Asset，保留原 API Asset 信息，并外层标明来自 scan campaign：

```json
{
  "metadata": {
    "source_type": "scan_campaign",
    "candidate_source": "api_asset",
    "api_asset": {
      "source_type": "api_asset",
      "source_id": "ASSET_001",
      "asset_key": "user-service:POST:/api/users",
      "source_name": "user-service-openapi",
      "operation_id": "createUser"
    }
  }
}
```

## 6. API candidate 到 API Case IR v2 draft 映射

### 6.1 映射规则

| API candidate 字段 | API Case IR v2 字段 | 说明 |
|---|---|---|
| `id` | `metadata.candidate_id` | 保留候选 ID |
| `method` | `request.method` 和 legacy `method` | 统一大写 |
| `path` | `request.path`、`request.url` 和 legacy `url` | Phase 1 不拼接真实 base URL |
| `source` | `metadata.candidate_source` | 保留来源 |
| `source_ref` | `metadata.source_ref` | 原样保留 |
| `policy` | `metadata.policy` | 用于执行前确认 |
| `risk_reason` | `metadata.risk_reason` | 用于报告和确认页 |
| `conditions` | `metadata.conditions` | 条件允许项必须保留 |
| `recommended_assertions` | `assertion` / `json_assertions` | 转为断言草稿 |
| `recommended_extractions` | `extraction` / `extract` | 转为提取草稿 |

### 6.2 输出示例

```json
{
  "id": "STEP_API_CANDIDATE_001",
  "name": "新建用户",
  "description": "来自用户管理 Campaign 的 API 候选 step",
  "protocol": "API-IR",
  "version": "2.0",
  "step_type": "API",
  "request": {
    "method": "POST",
    "url": "/api/users",
    "path": "/api/users",
    "headers": {},
    "query_params": {},
    "path_params": {},
    "body": {},
    "timeout_ms": 30000,
    "content_type": "application/json"
  },
  "assertion": {
    "status_code": 201,
    "json_assertions": {
      "$.id": "exists"
    }
  },
  "extraction": {
    "created_user_id": "$.id"
  },
  "method": "POST",
  "url": "/api/users",
  "expected_status_code": 201,
  "json_assertions": {
    "$.id": "exists"
  },
  "extract": {
    "created_user_id": "$.id"
  },
  "metadata": {
    "source_type": "scan_campaign",
    "campaign_id": "CMP_DRAFT_001",
    "plan_id": "PLAN_001",
    "candidate_id": "API_CANDIDATE_001",
    "candidate_source": "api_asset",
    "policy": "confirmation_required",
    "risk_reason": "会写入 test_user_* 测试数据",
    "execution_allowed_in_phase": false
  }
}
```

## 7. UI flow 到 Visual UI Case draft 映射

### 7.1 映射规则

| UI flow 字段 | Visual UI Case draft 字段 | 说明 |
|---|---|---|
| `id` | `metadata.flow_id` | 保留 flow ID |
| `name` | `name` | 用作 UI case 名称 |
| `steps` | `steps` | 转成 Visual UI step 草稿 |
| `assertions` | `expected_results` 或断言 step | 作为自然语言断言 |
| `source` | `metadata.source` | 保留来源 |
| `policy` | `metadata.policy` / step metadata | 每个 step 保留策略 |
| `risk_level` | `metadata.risk_level` | 用于确认页 |
| `requires_confirmation` | `metadata.requires_confirmation` | 写操作或提交动作必须保留 |

### 7.2 Visual UI step draft 示例

```json
{
  "name": "用户登录到用户列表",
  "description": "由 Campaign PLAN_001 生成的 UI 流程草稿",
  "base_url": "https://staging.example.com",
  "steps": [
    {
      "id": "UI_STEP_001",
      "action": "GOTO",
      "target": "/login",
      "value": "",
      "description": "打开登录页",
      "metadata": {
        "campaign_id": "CMP_DRAFT_001",
        "plan_id": "PLAN_001",
        "flow_id": "UI_FLOW_001",
        "policy": "allowed",
        "risk_level": "low",
        "requires_confirmation": false,
        "execution_allowed_in_phase": false
      }
    }
  ],
  "metadata": {
    "source_type": "scan_campaign",
    "campaign_id": "CMP_DRAFT_001",
    "plan_id": "PLAN_001",
    "flow_id": "UI_FLOW_001",
    "execution_allowed_in_phase": false
  }
}
```

## 8. 哪些 step 只能生成 draft，不能执行

Phase 1 所有生成的 API/UI 资产都只能是 draft，不能进入真实执行。但为了 Phase 2/3 铺路，需要进一步标注未来是否可执行。

| step 类型 | Phase 1 行为 | 未来可执行条件 |
|---|---|---|
| `policy=allowed` 的只读 GET/API 或只读 UI step | 生成 draft | Phase 2 确认后可执行 |
| `policy=confirmation_required` | 生成 draft + 人工复核项 | 用户逐项确认后可执行 |
| `policy=conditional_allowed` 且条件通过 | 生成 draft + 条件记录 | 条件仍有效且用户确认后可执行 |
| `policy=conditional_allowed` 但条件未通过 | 只生成计划项，不生成可执行 step | 条件补齐后重新生成 |
| `policy=forbidden` | 不生成 step，只保留风险项 | 不能执行 |
| `policy=out_of_scope` | 不生成 step，只保留拦截项 | 修改 Campaign scope 后重试 |
| source=`ai_inferred` 且 confidence < 0.7 | 不生成 step，只展示 | 提供 API Asset / Network 证据后重试 |

## 9. Phase 1 后端接口草案

统一前缀建议：`/api/v1/scan-campaigns`。

### 9.1 Campaign draft CRUD

#### `POST /scan-campaigns`

创建 Campaign draft。

请求体：Campaign draft 中除 `id`、`status`、`ai_plan_id`、时间字段外的用户输入字段。

响应：

```json
{
  "id": "CMP_DRAFT_001",
  "status": "draft"
}
```

#### `GET /scan-campaigns`

分页查询 Campaign draft。

查询参数：
- `page`
- `page_size`
- `status`
- `keyword`
- `scan_mode`

#### `GET /scan-campaigns/{campaign_id}`

获取 Campaign draft 详情。

#### `PUT /scan-campaigns/{campaign_id}`

更新 Campaign draft。只有 `draft` 和 `needs_revision` 状态允许更新。

#### `DELETE /scan-campaigns/{campaign_id}`

删除 Campaign draft。Phase 1 删除只影响 draft 和 plan，不影响 Test Case 或 Execution。

### 9.2 生成 AI plan

#### `POST /scan-campaigns/{campaign_id}/generate-plan`

根据 Campaign draft 生成 AI plan response。

请求体：

```json
{
  "regenerate": false,
  "notes": "优先复用 API Asset"
}
```

响应：AI plan response schema。

规则：
- 不执行测试。
- 不自动保存 API Case / UI Case。
- 不调用 Left Pupil / Right Pupil。
- 只生成计划、候选项、风险项和人工复核项。

### 9.3 获取 plan

#### `GET /scan-campaigns/{campaign_id}/plan`

获取最新 AI plan。

#### `GET /scan-campaigns/{campaign_id}/plans/{plan_id}`

获取指定版本 AI plan。

### 9.4 更新人工确认项

#### `PATCH /scan-campaigns/{campaign_id}/plans/{plan_id}/review-items/{review_item_id}`

更新单个人工复核项选择。

请求体：

```json
{
  "choice": "generate_asset_only",
  "comment": "允许生成资产草稿，但暂不执行"
}
```

可选 `choice`：
- `skip`
- `generate_asset_only`
- `approve_for_future_execution`

响应：更新后的 review item。

### 9.5 生成资产草稿

#### `POST /scan-campaigns/{campaign_id}/plans/{plan_id}/generate-asset-drafts`

根据 AI plan 和人工确认结果生成 API/UI 资产草稿。

请求体：

```json
{
  "asset_types": ["api_case_ir", "visual_ui_case"],
  "include_only_approved": true
}
```

响应：

```json
{
  "api_case_ir_steps": [],
  "visual_ui_cases": [],
  "skipped_items": []
}
```

规则：
- Phase 1 只返回草稿结构，不创建正式 TestCase，除非后续明确增加保存动作。
- `policy=forbidden` 和 `policy=out_of_scope` 永远进入 `skipped_items`。
- 所有草稿必须带 `metadata.execution_allowed_in_phase=false`。

## 10. 明确不提供的接口

Phase 1 不提供：

| 接口 | 不提供原因 |
|---|---|
| `POST /scan-campaigns/{id}/execute` | Phase 1 不执行测试 |
| `POST /scan-campaigns/{id}/run` | Phase 1 不调用执行引擎 |
| `POST /scan-campaigns/{id}/schedule` | 不做定时扫描 |
| `POST /scan-campaigns/{id}/attack-scan` | 不做攻击式扫描 |
| `POST /scan-campaigns/{id}/crawl-all` | 不做全站无限爬取 |

## 11. 进入实现前的剩余设计项

- API Asset 匹配结果的低保真 UI 布局。
- 执行前确认页的低保真 UI 布局。
- Campaign draft 与 AI plan 的数据库表设计。
- Phase 1 后端 service 边界。
- Phase 1 前端 service 边界。
