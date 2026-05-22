# UI + API 智能扫描 Phase 1 页面信息结构

## 1. Phase 1 定位

Phase 1 只做 Campaign 创建、计划生成、风险展示和人工确认页设计，不做自动执行。

核心原则：
- 先让用户把范围说清楚。
- 先让 AI 把计划讲清楚。
- 先让系统把风险拦住。
- 不把“生成计划”偷换成“直接执行”。

## 2. Phase 1 页面清单

| 页面 | 目的 | 是否执行测试 |
|---|---|---|
| Campaign 创建页 | 收集 URL、范围、模式、强度、安全约束 | 否 |
| AI 计划预览页 | 展示 UI/API 候选步骤、风险和不执行项 | 否 |
| 执行前确认页 | 让用户逐项确认写操作、条件允许项和风险项 | 否，Phase 1 只设计结构 |

Phase 1 的成功标准不是“能跑测试”，而是“用户能明确知道将来会测什么、不会测什么、哪些需要确认”。

## 3. Campaign 创建页字段结构

### 3.1 基础信息

| 字段 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|
| Campaign 名称 | text | 是 | 用户管理 Smoke 灰盒扫描 | 默认可由业务模块 + 强度 + 模式生成 |
| 目标 URL | url | 是 | https://staging.example.com | 必须命中 allowed_domains |
| 业务模块 | text | 是 | 用户管理 | 用于生成计划标题和资产命名 |
| 测试范围 | textarea | 是 | 登录、用户列表、新建用户 | 自然语言描述必须覆盖项 |
| 不测试范围 | textarea | 是 | 删除用户、重置密码、发送邀请短信 | 明确排除项 |
| 补充说明 | textarea | 否 | 使用默认测试账号 | 传给 AI 的额外上下文 |

### 3.2 测试策略

| 字段 | 类型 | 必填 | 选项 | 说明 |
|---|---|---|---|---|
| 测试模式 | select | 是 | 黑盒 / 灰盒 / 白盒 | Phase 1 推荐默认灰盒 |
| 测试强度 | select | 是 | Smoke / Regression / Deep | Deep 默认禁用执行，只生成计划 |
| 输出目标 | multi-select | 是 | 测试计划 / API 资产草稿 / UI 资产草稿 / 执行前检查表 | Phase 1 默认只选测试计划和检查表 |
| 是否生成资产草稿 | switch | 否 | 是 / 否 | Phase 1 可先只生成候选结构，不写库 |

### 3.3 范围边界

| 字段 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|
| 允许域名 | tags | 是 | staging.example.com | 所有 URL 和 API 候选必须命中 |
| 允许路径 | tags | 是 | /login, /users, /api/users | 限制页面和接口范围 |
| 最大页面数 | number | 是 | 10 | 防止黑盒扫描扩散 |
| 最大接口数 | number | 是 | 20 | 防止 API 候选无限扩张 |
| 最大计划步骤数 | number | 是 | 30 | 控制计划可读性 |

### 3.4 动作策略

| 字段 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|
| 禁止动作 | tags | 是 | delete, payment, send_sms | 永不自动执行，只列入不执行项 |
| 需确认动作 | tags | 否 | POST /api/users, export | 生成 draft，执行前逐项确认 |
| 条件允许动作 | textarea | 否 | 仅允许写入 test_user_* | 满足条件后可列为候选执行 |
| 是否允许表单提交 | select | 是 | 否 / 需要确认 / 是 | 默认需要确认 |
| 是否允许写 API | select | 是 | 否 / 需要确认 / 是 | POST/PUT/PATCH/DELETE 默认需要确认 |

### 3.5 数据与环境

| 字段 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|
| 环境安全标记 | select | 是 | sandbox / staging / production-readonly | production-readonly 不允许写操作 |
| 测试账号来源 | select | 否 | 环境变量 / 手动输入 / 不需要 | 不在报告中展示敏感值 |
| 数据写入策略 | select | 是 | 禁止写入 / 允许测试数据写入 / 仅沙箱写入 | 决定写操作是否能进入候选 |
| 测试数据标识 | text | 条件必填 | test_user_*, test_product_id=xxx | 写操作或条件允许动作必填 |
| 清理策略 | select | 条件必填 | 无需清理 / 自动清理 / 人工清理 | 写操作必填 |

### 3.6 特殊动作限制

| 字段 | 类型 | 适用场景 | 示例 | 说明 |
|---|---|---|---|---|
| 文件上传允许类型 | tags | 文件上传 | png, jpg, webp | 不允许可执行文件 |
| 文件上传最大大小 | number | 文件上传 | 2MB | 超限不生成候选 step |
| 测试文件目录 | path/text | 文件上传 | test-assets/uploads/ | 不允许读取任意本机文件 |
| 导出最大行数 | number | 数据导出 | 100 | 限制导出范围 |
| 导出字段白名单 | tags | 数据导出 | order_id, status, amount_masked | 防止敏感字段导出 |
| 是否允许下载落盘 | select | 数据导出 | 否 / 临时目录 / 是 | 默认临时目录或否 |
| 支付 provider 限制 | select | 支付相关 | mock / sandbox / 禁止 | 真实支付永远禁止 |

## 4. Campaign 创建页布局建议

```text
[页面标题] 新建智能扫描 Campaign
[说明] 只生成测试计划和执行前检查表，不会自动执行。

步骤 1：基础信息
  - Campaign 名称
  - 目标 URL
  - 业务模块
  - 测试范围
  - 不测试范围

步骤 2：范围边界
  - 允许域名
  - 允许路径
  - 最大页面数 / 最大接口数 / 最大步骤数

步骤 3：动作策略
  - 禁止动作
  - 需确认动作
  - 条件允许动作
  - 是否允许表单提交 / 写 API

步骤 4：数据与环境
  - 环境安全标记
  - 数据写入策略
  - 测试数据标识
  - 清理策略

步骤 5：特殊限制
  - 文件上传限制
  - 导出限制
  - 支付限制

底部操作：
  - 保存草稿
  - 生成测试计划
  - 取消
```

## 5. AI 计划预览页信息结构

### 5.1 顶部摘要

| 信息 | 示例 |
|---|---|
| Campaign 名称 | 用户管理 Smoke 灰盒扫描 |
| 状态 | Draft / Plan Generated |
| 测试模式 | 灰盒 |
| 测试强度 | Smoke |
| 执行状态 | 未执行 |
| 风险等级 | 中 |

### 5.2 范围确认卡片

展示：
- 包含范围。
- 排除范围。
- 允许域名。
- 允许路径。
- 超出范围并被拦截的候选项。

### 5.3 UI 候选流程

每个 UI flow 展示：
- flow 名称。
- step 列表。
- 页面/路径。
- 动作类型。
- 是否只读。
- 是否需要确认。
- 对应风险说明。

### 5.4 API 候选步骤

每个 API step 展示：
- method。
- path。
- 来源：API Asset / 浏览器 Network / AI 推断 / 现有 Test Case。
- 是否命中 allowed_paths。
- 动作策略：禁止 / 需确认 / 条件允许。
- 建议断言。
- 建议变量提取。
- 是否可生成 API Case IR v2。

### 5.5 风险与拦截项

按三层展示：

```text
禁止执行：
- DELETE /api/users/{id}：用户明确排除删除用户。
- POST /api/payments/charge：真实支付动作禁止。

需要确认：
- POST /api/users：会写入 test_user_* 数据。
- POST /api/reports/export：会导出数据。

条件允许：
- POST /api/payments/mock：仅当 provider=mock 且 environment=sandbox。
```

### 5.6 人工复核项

每项必须包含：
- 为什么需要人工确认。
- 用户确认后会发生什么。
- 不确认时如何降级。

## 6. 执行前确认页信息结构

Phase 1 只设计确认页结构，不实现执行。

### 6.1 页面目标

执行前确认页不是“确认弹窗”，而是一个风险复核页面。它必须让用户在执行前看见：
- 即将执行哪些 UI steps。
- 即将执行哪些 API steps。
- 哪些步骤会写入数据。
- 哪些步骤会上传、导出或下载。
- 哪些步骤被禁止执行。
- 条件允许项是否满足条件。

### 6.2 顶部执行摘要

| 字段 | 示例 |
|---|---|
| Campaign | 用户管理 Smoke 灰盒扫描 |
| 即将执行 UI steps | 8 |
| 即将执行 API steps | 3 |
| 写操作数量 | 1 |
| 上传/导出数量 | 0 |
| 禁止项数量 | 3 |
| 需确认项数量 | 1 |
| 条件允许项数量 | 0 |

### 6.3 逐项确认表

| 字段 | 说明 |
|---|---|
| Step | UI/API step 名称 |
| 类型 | UI / API |
| 动作 | GET / POST / CLICK / TYPE / UPLOAD / EXPORT |
| 目标 | 页面路径或 API path |
| 策略 | 禁止 / 需确认 / 条件允许 |
| 风险 | 数据写入、导出、支付、消息发送等 |
| 条件 | test_* 数据、sandbox、字段白名单等 |
| 用户选择 | 跳过 / 允许 / 仅生成资产 |

### 6.4 禁止项展示

禁止项不能提供“允许执行”按钮，只能：
- 保留在计划中。
- 标记为不执行。
- 允许用户编辑 Campaign 范围后重新生成计划。

### 6.5 条件允许项校验

条件允许项必须展示条件是否满足：

| 条件 | 状态 | 示例 |
|---|---|---|
| 环境非生产 | 通过 | staging |
| 数据标识存在 | 通过 | test_user_* |
| 清理策略存在 | 通过 | 人工清理 |
| provider 为 mock | 未通过 | 未检测到 provider 标记 |

只有全部条件通过，才允许进入候选执行列表。

### 6.6 底部操作

Phase 1 设计态：
- 保存确认草稿。
- 返回修改 Campaign。
- 生成资产草稿。

Phase 2/3 才考虑：
- 开始执行。

## 7. Campaign draft 数据结构

Campaign draft 是 Phase 1 的核心持久化对象，用于保存用户输入、范围边界、动作策略和 AI 计划状态。它不是执行记录，也不代表任何测试已经运行。

### 7.1 顶层结构

```json
{
  "id": "CMP_DRAFT_001",
  "name": "用户管理 Smoke 灰盒扫描",
  "status": "draft",
  "target": {
    "base_url": "https://staging.example.com",
    "business_module": "用户管理",
    "scope_text": "登录、用户列表、新建用户",
    "out_of_scope_text": "删除用户、重置密码、发送邀请短信",
    "notes": "使用默认测试账号"
  },
  "strategy": {
    "scan_mode": "graybox",
    "intensity": "smoke",
    "output_goals": ["test_plan", "pre_execution_checklist"],
    "generate_asset_drafts": false
  },
  "boundaries": {
    "allowed_domains": ["staging.example.com"],
    "allowed_paths": ["/login", "/users", "/api/users"],
    "max_pages": 10,
    "max_api_candidates": 20,
    "max_plan_steps": 30
  },
  "action_policy": {
    "forbidden_actions": ["delete", "payment", "send_sms", "send_email"],
    "confirmation_required_actions": ["POST /api/users"],
    "conditional_allowed_actions": ["仅允许写入 test_user_* 测试数据"],
    "form_submit_policy": "confirm_required",
    "write_api_policy": "confirm_required"
  },
  "data_policy": {
    "environment_safety": "staging",
    "credential_source": "environment",
    "write_policy": "allow_test_data",
    "test_data_markers": ["test_user_*"],
    "cleanup_policy": "manual_cleanup"
  },
  "special_limits": {
    "upload": {
      "allowed_types": ["png", "jpg", "webp"],
      "max_size_mb": 2,
      "test_file_dir": "test-assets/uploads/"
    },
    "export": {
      "max_rows": 100,
      "field_allowlist": ["order_id", "status", "created_at", "amount_masked"],
      "download_policy": "temporary_dir_only"
    },
    "payment": {
      "provider_policy": "mock_or_sandbox_only"
    }
  },
  "ai_plan_id": null,
  "created_at": "2026-05-22T00:00:00Z",
  "updated_at": "2026-05-22T00:00:00Z"
}
```

### 7.2 字段约束

| 字段 | 约束 |
|---|---|
| `status` | Phase 1 只允许 `draft`、`plan_generated`、`needs_revision` |
| `target.base_url` | 必须命中 `boundaries.allowed_domains` |
| `boundaries.allowed_domains` | 至少 1 个，不允许通配所有域名 |
| `boundaries.allowed_paths` | 至少 1 个，不允许空 scope 自动扫描 |
| `strategy.intensity=deep` | Phase 1 只生成计划，不生成执行候选 |
| `data_policy.environment_safety=production-readonly` | 所有写操作必须降级为禁止或只生成资产草稿 |
| `action_policy.forbidden_actions` | 禁止项不能在确认页出现“允许执行”按钮 |
| `special_limits.upload` | 只有扫描范围涉及上传时必填 |
| `special_limits.export` | 只有扫描范围涉及导出时必填 |
| `special_limits.payment` | 只有扫描范围涉及支付时必填 |

## 8. AI plan response schema

AI plan response 是生成计划接口的返回结构。它必须可被前端直接渲染为计划预览页和执行前确认页，也必须能追溯每个候选 step 的来源和风险策略。

### 8.1 顶层结构

```json
{
  "plan_id": "PLAN_001",
  "campaign_draft_id": "CMP_DRAFT_001",
  "status": "generated",
  "summary": {
    "title": "用户管理 Smoke 灰盒扫描计划",
    "scan_mode": "graybox",
    "intensity": "smoke",
    "risk_level": "medium",
    "execution_state": "not_executed"
  },
  "scope_review": {
    "included": ["登录", "用户列表", "新建用户"],
    "excluded": ["删除用户", "重置密码", "发送邀请短信"],
    "allowed_domains": ["staging.example.com"],
    "allowed_paths": ["/login", "/users", "/api/users"],
    "blocked_out_of_scope": [
      {
        "target": "DELETE /api/users/{id}",
        "reason": "用户明确排除删除用户"
      }
    ]
  },
  "ui_flows": [],
  "api_candidates": [],
  "risk_items": [],
  "manual_review_items": [],
  "asset_drafts": {
    "api_case_ir_steps": [],
    "visual_ui_steps": []
  },
  "coverage_summary": {
    "planned_modules": 3,
    "ui_flow_count": 1,
    "api_candidate_count": 3,
    "blocked_count": 3,
    "confirmation_required_count": 1,
    "conditional_allowed_count": 0
  }
}
```

### 8.2 UI flow item schema

```json
{
  "id": "UI_FLOW_001",
  "name": "用户登录到用户列表",
  "source": "ai_generated",
  "steps": [
    {
      "id": "UI_STEP_001",
      "action": "GOTO",
      "target": "/login",
      "description": "打开登录页",
      "policy": "allowed",
      "risk_level": "low",
      "requires_confirmation": false
    }
  ],
  "assertions": [
    "登录成功后进入用户管理页面",
    "用户列表可见"
  ],
  "can_generate_visual_case": true
}
```

### 8.3 API candidate item schema

```json
{
  "id": "API_CANDIDATE_001",
  "method": "POST",
  "path": "/api/users",
  "source": "api_asset",
  "source_ref": {
    "asset_id": "ASSET_001",
    "operation_id": "createUser"
  },
  "policy": "confirmation_required",
  "risk_level": "medium",
  "risk_reason": "会写入 test_user_* 测试数据",
  "conditions": [
    {
      "name": "环境非生产",
      "status": "passed",
      "detail": "staging"
    },
    {
      "name": "测试数据标识存在",
      "status": "passed",
      "detail": "test_user_*"
    },
    {
      "name": "清理策略存在",
      "status": "passed",
      "detail": "manual_cleanup"
    }
  ],
  "recommended_assertions": [
    {
      "type": "status_code",
      "expected": 201
    },
    {
      "type": "json_path",
      "path": "$.id",
      "expected": "exists"
    }
  ],
  "recommended_extractions": {
    "created_user_id": "$.id"
  },
  "can_generate_api_case_ir": true
}
```

### 8.4 Risk item schema

```json
{
  "id": "RISK_001",
  "target": "DELETE /api/users/{id}",
  "category": "destructive_action",
  "policy": "forbidden",
  "severity": "high",
  "reason": "用户明确排除删除用户，且删除动作默认禁止自动执行",
  "user_visible_message": "删除用户已被列为不执行项，不会生成可执行 step。",
  "resolution": "如确需测试删除，请改用测试数据并在 Campaign 中设置条件允许动作。"
}
```

### 8.5 Manual review item schema

```json
{
  "id": "REVIEW_001",
  "target_type": "api_candidate",
  "target_id": "API_CANDIDATE_001",
  "title": "确认是否允许创建测试用户",
  "reason": "该步骤会写入 test_user_* 数据",
  "if_approved": "生成 API Case IR v2 draft，但 Phase 1 不执行",
  "if_rejected": "保留用户列表只读测试，跳过新建用户步骤",
  "available_choices": ["skip", "generate_asset_only", "approve_for_future_execution"]
}
```

### 8.6 Policy 枚举

| policy | 含义 | Phase 1 行为 |
|---|---|---|
| `allowed` | 只读或无副作用动作 | 可进入候选计划 |
| `confirmation_required` | 写入、上传、导出或状态变化 | 必须进入人工复核项 |
| `conditional_allowed` | 条件满足后可候选执行 | 必须展示条件校验结果 |
| `forbidden` | 禁止动作或超出范围 | 只展示，不允许执行 |
| `out_of_scope` | 超出用户范围 | 拦截并提示修改 Campaign |

## 9. Phase 1 验收标准

Phase 1 完成时必须满足：

- Campaign 创建页字段能覆盖 Phase 0 模板所有约束。
- AI 计划预览页能展示范围、UI/API 候选、风险、禁止项和人工复核项。
- 执行前确认页能区分禁止、需确认、条件允许。
- 所有写操作都能被识别并进入确认流程。
- 不提供绕过禁止项的执行按钮。
- 至少用 Phase 0 的 10 个样例验证页面字段够用。

## 10. 不做事项

Phase 1 不做：
- 不执行 Campaign。
- 不直接调用 Left Pupil / Right Pupil。
- 不生成真实执行记录。
- 不自动保存 API Case / UI Case。
- 不做全站爬取。
- 不做攻击式安全扫描。

## 11. 下一步设计任务

进入实现前还需要补充：
1. API Asset 匹配展示规则。
2. “生成资产草稿”的数据映射规则。
3. Phase 1 页面原型或低保真布局。
4. Campaign draft 与 AI plan 的后端接口草案。
