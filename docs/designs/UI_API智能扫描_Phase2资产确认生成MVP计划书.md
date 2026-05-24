# UI + API 智能扫描 Phase 2 资产确认生成 MVP 计划书

## 1. 阶段定位

Phase 2 的目标是把 Phase 1 生成的资产草稿，在用户明确确认后提升为正式可编辑测试资产。

Phase 2 只解决“草稿 → 正式资产”的保存闭环，不解决 Campaign 执行。

本阶段允许：
- 从 Scan Campaign asset draft 生成正式 API Auto TestCase。
- 从 Scan Campaign asset draft 生成正式 Visual UI Case。
- 在 API Auto / Visual UI 页面继续编辑这些资产。
- 保留 Campaign、Plan、Review、Asset Draft 的来源追踪 metadata。

本阶段不允许：
- 不自动执行 Campaign。
- 不自动执行 API TestCase。
- 不自动执行 Visual UI Case。
- 不创建 Execution。
- 不出现“开始执行 Campaign / 一键扫描并执行”等入口。
- 不把 `approve_for_future_execution` 当成立即执行授权。

## 2. Phase 1 到 Phase 2 的边界变化

| 能力 | Phase 1 | Phase 2 |
| --- | --- | --- |
| Campaign draft | 支持 | 支持 |
| AI plan | 支持 | 支持 |
| 人工复核 | 支持 | 支持 |
| API Case IR v2 草稿 | 支持预览 | 支持保存为正式 TestCase |
| Visual UI Case 草稿 | 支持预览 | 支持保存为正式 Visual UI Case |
| 正式资产编辑 | 不支持 | 支持跳转到 API Auto / Visual UI 编辑 |
| Campaign 执行 | 不支持 | 不支持 |
| Execution 创建 | 不支持 | 不支持 |

## 3. 核心目标

1. 用户能明确看到哪些草稿可保存为正式资产。
2. 用户必须手动确认后才能保存正式资产。
3. 保存后的资产能在 API Auto / Visual UI 中继续编辑。
4. 保存后的资产保留完整来源：Campaign、Plan、Review、Asset Draft、API Asset source_ref。
5. 保存动作不能触发执行。
6. 重复保存要可控，避免生成大量重复资产。

## 4. 用户流程

### 4.1 主流程

```text
Campaign 草稿
  ↓
生成 AI 计划
  ↓
人工复核
  ↓
生成资产草稿预览
  ↓
用户勾选草稿
  ↓
确认保存为正式资产
  ↓
生成 API Auto TestCase / Visual UI Case
  ↓
跳转到对应编辑页继续完善
```

### 4.2 页面流程

```text
┌─────────────────────────────────────────────────────────────┐
│ 资产草稿预览                                                 │
│ 说明：草稿不会执行；保存为正式资产后仍需人工编辑和单独执行。     │
├─────────────────────────────────────────────────────────────┤
│ [ ] API Case IR v2: POST /api/users                          │
│     来源：API Asset / smart-scan-ui-click-smoke               │
│     策略：confirmation_required                               │
│     风险：写操作会修改测试数据                                 │
│     metadata: campaign_id / plan_id / source_ref              │
│     [查看 JSON] [编辑名称]                                     │
│                                                             │
│ [ ] Visual UI Case: 用户管理 范围冒烟流程                       │
│     来源：Campaign UI Flow                                    │
│     策略：allowed                                             │
│     步骤：2                                                   │
│     [查看 JSON] [编辑名称]                                     │
├─────────────────────────────────────────────────────────────┤
│ 已选择 2 个草稿                                               │
│ [保存为正式资产]                                               │
└─────────────────────────────────────────────────────────────┘
```

确认弹窗：

```text
确认保存为正式资产？

将创建：
- API Auto TestCase：1 个
- Visual UI Case：1 个

这些资产会进入正式资产库，但不会自动执行。
执行需要后续在 API Auto / Visual UI / Execution 中单独触发。

[取消] [确认保存]
```

## 5. 资产保存规则

### 5.1 API Case IR v2 草稿保存为 TestCase

输入：
- `scan_campaign_asset_drafts.asset_type = api_case_ir`
- 或 plan response 中的 `asset_drafts.api_case_ir_steps[]`

输出：
- 正式 API Auto TestCase。
- TestCase step 使用 API Case IR v2 内部标准结构。

必须保留字段：

| 字段 | 保存位置 | 说明 |
| --- | --- | --- |
| `protocol` | step payload | 必须是 `API-IR` |
| `version` | step payload | 必须是 `2.0` |
| `method` | step request | HTTP method |
| `url/path` | step request | API path |
| `headers` | step request | headers |
| `query_params` | step request | query |
| `path_params` | step request | path params |
| `body` | step request | request body |
| `assertions` | step assertions | status/json/header assertions |
| `metadata.source_type` | metadata | `scan_campaign` |
| `metadata.campaign_id` | metadata | 来源 Campaign |
| `metadata.plan_id` | metadata | 来源 Plan |
| `metadata.candidate_id` | metadata | 来源候选项 |
| `metadata.candidate_source` | metadata | `api_asset` / `network` / `ai_inferred` / `test_case` |
| `metadata.source_ref` | metadata | 原始资产引用 |
| `metadata.policy` | metadata | 风险策略 |
| `metadata.risk_reason` | metadata | 风险原因 |
| `metadata.conditions` | metadata | 条件允许说明 |
| `metadata.review_choice` | metadata | 人工复核选择 |
| `metadata.execution_allowed_in_phase` | metadata | Phase 2 仍为 `false` |

命名建议：

```text
[Smart Scan] {business_module} - {method} {path}
```

示例：

```text
[Smart Scan] 用户管理 - POST /api/users
```

### 5.2 Visual UI 草稿保存为 Visual UI Case

输入：
- `scan_campaign_asset_drafts.asset_type = visual_ui_case`
- 或 plan response 中的 `asset_drafts.visual_ui_steps[]`

输出：
- 正式 Visual UI Case。

必须保留字段：

| 字段 | 保存位置 | 说明 |
| --- | --- | --- |
| `name` | case name | UI 用例名称 |
| `description` | case description | 来源说明 |
| `base_url` | case config | 目标 URL |
| `steps` | case steps | UI steps |
| `expected_results` | case expected | 预期结果 |
| `metadata.source_type` | metadata | `scan_campaign` |
| `metadata.campaign_id` | metadata | 来源 Campaign |
| `metadata.plan_id` | metadata | 来源 Plan |
| `metadata.flow_id` | metadata | 来源 UI flow |
| `metadata.policy` | metadata | 风险策略 |
| `metadata.risk_level` | metadata | 风险级别 |
| `metadata.execution_allowed_in_phase` | metadata | Phase 2 仍为 `false` |

命名建议：

```text
[Smart Scan] {business_module} - {flow_name}
```

示例：

```text
[Smart Scan] 用户管理 - 范围冒烟流程
```

## 6. 保存前校验

### 6.1 API TestCase 校验

保存前必须校验：

- `protocol = API-IR`。
- `version = 2.0`。
- `method` 不为空。
- `url/path` 不为空。
- `metadata.campaign_id` 不为空。
- `metadata.plan_id` 不为空。
- `metadata.source_type = scan_campaign`。
- `metadata.execution_allowed_in_phase = false`。
- `policy=forbidden` 或 `policy=out_of_scope` 的草稿不能保存为正式资产。

可保存策略：

| policy | 是否可保存正式资产 | 说明 |
| --- | --- | --- |
| `allowed` | 可以 | 只保存，不执行 |
| `conditional_allowed` | 可以 | 必须保留 conditions |
| `confirmation_required` | 可以 | 必须有 review choice |
| `forbidden` | 不可以 | 禁止保存为正式资产 |
| `out_of_scope` | 不可以 | 超出授权范围 |

### 6.2 Review choice 校验

| choice | 是否可保存正式资产 | 说明 |
| --- | --- | --- |
| `pending` | 不可以 | 需要先人工复核 |
| `skip` | 不可以 | 用户明确跳过 |
| `generate_asset_only` | 可以 | 推荐保存为正式资产 |
| `approve_for_future_execution` | 可以 | 只代表未来意向，不执行 |

`approve_for_future_execution` 保存时必须展示提示：

```text
该选择只会保存正式资产和未来执行意向，不会在 Phase 2 执行测试。
```

### 6.3 Visual UI Case 校验

保存前必须校验：

- `base_url` 不为空。
- 至少有一个 UI step。
- 每个 step 有 `action`。
- 每个 step 保留 metadata。
- `execution_allowed_in_phase = false`。
- 禁止保存包含明显危险动作的 UI flow：删除、支付、发短信、发邮件、权限变更。

## 7. 重复保存策略

必须避免同一 Campaign draft 被反复保存成重复资产。

推荐后端记录映射关系：

```text
scan_campaign_asset_draft_id
  → generated_asset_type
  → generated_asset_id
```

或者在正式资产 metadata 中记录：

```json
{
  "source_type": "scan_campaign",
  "campaign_id": "CMP-...",
  "plan_id": "PLAN-...",
  "asset_draft_id": "DRAFT-..."
}
```

重复保存处理：

| 场景 | 行为 |
| --- | --- |
| 草稿从未保存 | 创建正式资产 |
| 草稿已保存且未选择覆盖 | 显示已保存状态和跳转链接 |
| 用户选择另存为新资产 | 创建新资产，但 metadata 记录 duplicated_from |
| 用户选择覆盖 | Phase 2 MVP 暂不支持，后续再做 |

Phase 2 MVP 推荐只实现：
- 首次保存。
- 已保存后显示正式资产链接。
- 不支持覆盖。

## 8. 后端接口草案

### 8.1 保存单个草稿为正式资产

```http
POST /api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/asset-drafts/{draft_id}/promote
```

请求：

```json
{
  "asset_type": "api_case_ir",
  "name": "[Smart Scan] 用户管理 - POST /api/users",
  "description": "由 Smart Scan Campaign 生成",
  "confirm_no_execution": true
}
```

响应：

```json
{
  "campaign_id": "CMP-...",
  "plan_id": "PLAN-...",
  "draft_id": "DRAFT-...",
  "generated_asset_type": "test_case",
  "generated_asset_id": "TC-...",
  "status": "created",
  "execution_created": false,
  "execution_allowed_in_phase": false
}
```

### 8.2 批量保存草稿为正式资产

```http
POST /api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/asset-drafts/promote-batch
```

请求：

```json
{
  "items": [
    {
      "draft_id": "DRAFT-API-001",
      "asset_type": "api_case_ir",
      "name": "[Smart Scan] 用户管理 - POST /api/users"
    },
    {
      "draft_id": "DRAFT-UI-001",
      "asset_type": "visual_ui_case",
      "name": "[Smart Scan] 用户管理 - 范围冒烟流程"
    }
  ],
  "confirm_no_execution": true
}
```

响应：

```json
{
  "created": [
    {
      "draft_id": "DRAFT-API-001",
      "generated_asset_type": "test_case",
      "generated_asset_id": "TC-..."
    }
  ],
  "skipped": [
    {
      "draft_id": "DRAFT-UI-001",
      "reason": "already_promoted"
    }
  ],
  "execution_created": false
}
```

### 8.3 获取草稿提升状态

```http
GET /api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/asset-drafts/promotions
```

响应：

```json
{
  "items": [
    {
      "draft_id": "DRAFT-API-001",
      "asset_type": "api_case_ir",
      "promoted": true,
      "generated_asset_type": "test_case",
      "generated_asset_id": "TC-...",
      "created_at": "2026-05-24T00:00:00"
    }
  ]
}
```

## 9. 数据模型草案

推荐新增表：`scan_campaign_asset_promotions`

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | promotion id |
| `campaign_id` | string | Campaign ID |
| `plan_id` | string | Plan ID |
| `asset_draft_id` | string | Asset Draft ID |
| `draft_type` | string | `api_case_ir` / `visual_ui_case` |
| `generated_asset_type` | string | `test_case` / `visual_ui_case` |
| `generated_asset_id` | string | 正式资产 ID |
| `status` | string | `created` / `skipped` / `failed` |
| `metadata` | json | 来源、策略、复核快照 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

唯一约束建议：

```text
unique(asset_draft_id, generated_asset_type)
```

如果暂时没有独立 draft row，也可以使用：

```text
unique(campaign_id, plan_id, draft_type, draft_ref)
```

## 10. 前端页面改造

### 10.1 资产草稿 Tab 增强

新增能力：

- 草稿列表 checkbox。
- 草稿名称编辑。
- 草稿类型 badge。
- 策略 badge。
- 来源信息展示。
- 已保存状态展示。
- 保存后跳转链接：
  - API TestCase → API Auto / Test Case 编辑页。
  - Visual UI Case → Visual UI 编辑页。

### 10.2 草稿详情 Drawer / Modal

点击“查看 JSON”展示：

- API Case IR v2 完整 JSON。
- Visual UI Case 完整 JSON。
- metadata 来源信息。
- policy / risk_reason / conditions。

只读展示，不允许直接在 JSON 中编辑。MVP 只允许编辑资产名称和描述。

### 10.3 保存确认弹窗

保存前必须展示：

- 即将创建的资产数量。
- 每个资产类型。
- 不会执行测试。
- 不能保存 forbidden/out_of_scope。
- 已保存过的草稿会跳过。

确认按钮文案：

```text
确认保存为正式资产
```

禁止使用：

```text
开始执行
立即运行
一键扫描
```

## 11. 与 API Auto / Visual UI 的集成

### 11.1 API Auto

保存 API Case 后：

- 在 API Auto / Test Case 列表中可见。
- 可进入编辑页修改步骤。
- step schema 必须是 API Case IR v2。
- metadata 中保留 Smart Scan 来源。

推荐在列表增加来源 badge：

```text
来源：Smart Scan
```

### 11.2 Visual UI

保存 Visual UI Case 后：

- 在 Visual UI 列表中可见。
- 可进入编辑页调整步骤和断言。
- metadata 中保留 Smart Scan 来源。

推荐在列表增加来源 badge：

```text
来源：Smart Scan
```

## 12. 安全边界

Phase 2 虽然创建正式资产，但仍然不是执行阶段。

必须保证：

- Promote 接口不创建 Execution。
- Promote 接口不调用 API 执行引擎。
- Promote 接口不调用 Visual UI 执行引擎。
- Promote 接口不访问目标 `base_url`。
- Promote 接口只写本地资产库。
- 正式资产 metadata 仍包含 `execution_allowed_in_phase=false`。

禁止保存为正式资产：

- `policy=forbidden`。
- `policy=out_of_scope`。
- 未复核的写操作。
- 缺失 `campaign_id` / `plan_id` / `source_ref` 的 API 草稿。

## 13. 验证方式

### 13.1 后端验证

1. 创建 Campaign。
2. 生成 Plan。
3. 保存 review choice 为 `generate_asset_only`。
4. 生成 asset drafts。
5. 调用 promote 接口。
6. 确认正式 TestCase 创建。
7. 确认正式 Visual UI Case 创建。
8. 确认没有 Execution 创建。
9. 确认 metadata 保留完整。
10. 重复 promote 同一 draft，确认不会重复创建。

必须检查：

```text
Execution count 不增加
TestCase count 增加
VisualUseCase count 增加
metadata.execution_allowed_in_phase == false
metadata.source_type == scan_campaign
```

### 13.2 前端真实点击 smoke

1. 打开 `/smart-scan`。
2. 选择已有 `asset_drafts_generated` Campaign。
3. 进入资产草稿 Tab。
4. 勾选一个 API Case IR v2 草稿。
5. 勾选一个 Visual UI 草稿。
6. 点击“保存为正式资产”。
7. 在确认弹窗中点击“确认保存”。
8. 页面显示保存成功和资产链接。
9. 点击 API Auto 链接，确认正式 TestCase 可见。
10. 点击 Visual UI 链接，确认正式 Visual UI Case 可见。
11. 确认页面没有 Campaign 执行入口。

### 13.3 安全 grep

```bash
rg "开始执行|立即运行|一键扫描|/executions|/run|/schedule|left-pupil|execute" frontend/src/app/smart-scan frontend/src/services/scanCampaignService.ts backend/app/api/v1/endpoints/scan_campaigns.py backend/app/services/scan_campaign_service.py
```

允许：
- 文档和错误提示里的禁止说明。
- `approve_for_future_execution` 字段名。

不允许：
- 新增 Campaign 执行接口。
- Promote 接口调用执行服务。

## 14. 退出标准

Phase 2 完成条件：

- 用户可以从 Smart Scan 资产草稿页面手动保存正式 API TestCase。
- 用户可以从 Smart Scan 资产草稿页面手动保存正式 Visual UI Case。
- 保存后的资产刷新后仍可查看。
- API Case IR v2 metadata/source_ref 不丢失。
- Visual UI Case metadata 不丢失。
- 重复保存不会创建不可控重复资产。
- 后端测试证明没有创建 Execution。
- 前端真实点击 smoke 通过。
- 页面无执行入口。

## 15. 非目标

Phase 2 不做：

- 不做 Campaign 执行按钮。
- 不做批量真实执行。
- 不做自动登录或自动爬取。
- 不做真实浏览器 Network 捕获。
- 不做 LLM 自动修复生成资产。
- 不做跨系统调度。
- 不做结果报告。

这些能力进入 Phase 3 或更后阶段。

## 16. 后续衔接

Phase 2 完成后进入 Phase 3：受控执行 MVP。

Phase 3 才考虑：
- Campaign 执行前确认页。
- Execution batch 关联。
- API/UI/HYBRID 执行结果汇总。
- 失败归因到 Campaign plan / UI step / API step。
- 覆盖范围报告。