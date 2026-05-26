# UI + API 智能扫描 Phase 1 后端表与接口设计

## 1. 文档定位

本文把 Phase 1 的后端实现边界落到数据库表、service 分层和接口处理流程。

Phase 1 后端只负责：
- 保存 Campaign draft。
- 生成并保存 AI plan。
- 保存人工复核选择。
- 生成 API/UI 资产草稿结构。
- 保留候选来源、风险策略和拦截原因。

Phase 1 后端不负责：
- 不执行 UI/API 测试。
- 不调用 Dispatcher、Left Pupil、Midscene 执行引擎。
- 不创建 Execution 记录。
- 不自动保存正式 TestCase / VisualUseCase。
- 不提供 execute、run、schedule、crawl-all、attack-scan 类接口。

## 2. 与现有后端风格对齐

当前后端实现特征：

| 现有模块 | 模式 | Phase 1 对齐方式 |
|---|---|---|
| `TestCase` | 字符串 ID、Enum 生命周期、复杂 steps 用 JSON 保存 | Campaign 和 plan 继续使用字符串 ID 与 JSON 字段承载复杂结构 |
| `ApiAsset` | `model + service + endpoint` 分层，列表分页和条件过滤 | Scan Campaign 采用同样分层 |
| `VisualUseCase` | UI 用例单独持久化，不混入 API case | Phase 1 只生成 Visual UI draft payload，不写入 `visual_use_cases` |
| `api_case_ir_converter` | API Case IR v2 标准化和 legacy 字段兼容 | 生成 API draft 时必须调用同类规范化逻辑 |
| `init_db()` | 启动时 `Base.metadata.create_all` 建表 | 新模型先纳入 Base；后续如引入 Alembic 再补迁移 |

建议新增代码路径：

| 文件 | 职责 |
|---|---|
| `backend/app/models/scan_campaign.py` | Scan Campaign、Plan、ReviewItem、AssetDraft ORM 模型 |
| `backend/app/schemas/scan_campaign.py` | 请求/响应 Pydantic schema |
| `backend/app/services/scan_campaign_service.py` | Campaign CRUD、计划生成、复核更新、草稿生成 |
| `backend/app/api/v1/endpoints/scan_campaigns.py` | `/api/v1/scan-campaigns` 路由 |
| `backend/app/api/v1/router.py` | 注册 `scan_campaigns` router |
| `backend/app/models/__init__.py` | 导出新增模型，确保 `init_db()` 能建表 |

## 3. 核心对象关系

```text
scan_campaigns 1 ── N scan_campaign_plans
scan_campaigns 1 ── N scan_campaign_review_items
scan_campaign_plans 1 ── N scan_campaign_review_items
scan_campaign_plans 1 ── N scan_campaign_asset_drafts
```

Phase 1 禁止出现的关系：

```text
scan_campaigns ──> executions
scan_campaign_plans ──> executions
scan_campaign_asset_drafts ──> test_cases
scan_campaign_asset_drafts ──> visual_use_cases
```

资产草稿只保留为 draft payload。是否提升为正式 TestCase / VisualUseCase，留给 Phase 2 之后的显式保存动作。

## 4. 表设计

### 4.1 `scan_campaigns`

保存用户输入、范围边界、动作策略和当前最新 plan 指针。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | String(50) | 是 | `CMP-` 前缀字符串 ID |
| `name` | String(200) | 是 | Campaign 名称 |
| `status` | Enum | 是 | `draft` / `plan_generated` / `needs_revision` / `archived` |
| `target` | JSON | 是 | `base_url`、业务模块、测试范围、不测试范围、补充说明 |
| `strategy` | JSON | 是 | 黑盒/灰盒/白盒、强度、输出目标、是否生成资产草稿 |
| `boundaries` | JSON | 是 | allowed domains/paths、最大页面数、最大接口数、最大步骤数 |
| `action_policy` | JSON | 是 | 禁止动作、需确认动作、条件允许动作、写 API / 表单策略 |
| `data_policy` | JSON | 是 | 环境安全标记、测试账号来源、写入策略、数据标识、清理策略 |
| `special_limits` | JSON | 是 | 上传、导出、支付等特殊限制 |
| `ai_plan_id` | String(50) | 否 | 当前最新 plan ID，不代表执行 |
| `search_text` | Text | 否 | 名称、模块、范围拼接，用于 keyword 查询 |
| `created_at` | DateTime(timezone=True) | 是 | 创建时间 |
| `updated_at` | DateTime(timezone=True) | 是 | 更新时间 |

建议索引：

| 索引 | 字段 | 用途 |
|---|---|---|
| `ix_scan_campaigns_status` | `status` | 列表按状态过滤 |
| `ix_scan_campaigns_updated_at` | `updated_at` | 列表默认倒序 |
| `ix_scan_campaigns_name` | `name` | keyword 初筛 |

### 4.2 `scan_campaign_plans`

保存每次生成的 AI plan 版本。一个 Campaign 可以多次 regenerate，旧 plan 标记为 superseded，不覆盖历史。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | String(50) | 是 | `PLAN-` 前缀字符串 ID |
| `campaign_id` | String(50) FK | 是 | 关联 `scan_campaigns.id` |
| `version` | Integer | 是 | 同一 Campaign 内从 1 递增 |
| `status` | Enum | 是 | `generated` / `review_saved` / `asset_drafts_generated` / `superseded` |
| `summary` | JSON | 是 | 标题、模式、强度、风险等级、执行状态 |
| `scope_review` | JSON | 是 | included/excluded/allowed/blocked 范围确认 |
| `ui_flows` | JSON | 是 | UI 候选流程数组 |
| `api_candidates` | JSON | 是 | API 候选步骤数组 |
| `risk_items` | JSON | 是 | 禁止、需确认、条件允许、越界风险项 |
| `coverage_summary` | JSON | 是 | planned_modules、candidate 计数、blocked 计数等 |
| `generation_metadata` | JSON | 是 | campaign snapshot、模型、prompt version、source counts |
| `created_at` | DateTime(timezone=True) | 是 | 创建时间 |
| `updated_at` | DateTime(timezone=True) | 是 | 更新时间 |

建议约束：

| 约束 | 说明 |
|---|---|
| unique(`campaign_id`, `version`) | 避免同一 Campaign 版本冲突 |
| FK `campaign_id` on delete cascade | 删除 Campaign draft 时同步删除 plan |

### 4.3 `scan_campaign_review_items`

保存人工复核项和用户选择。不要只把 review items 塞在 plan JSON 里，否则单项 PATCH 难以审计。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | String(50) | 是 | `REVIEW-` 前缀字符串 ID |
| `campaign_id` | String(50) FK | 是 | 冗余关联，便于查询 |
| `plan_id` | String(50) FK | 是 | 关联 plan |
| `target_type` | String(50) | 是 | `api_candidate` / `ui_step` / `ui_flow` / `risk_item` |
| `target_id` | String(100) | 是 | 对应 candidate/flow/risk item ID |
| `policy` | String(50) | 是 | `confirmation_required` / `conditional_allowed` 等 |
| `title` | String(200) | 是 | 展示标题 |
| `reason` | Text | 是 | 为什么需要确认 |
| `if_approved` | Text | 是 | 用户确认后会发生什么 |
| `if_rejected` | Text | 是 | 不确认如何降级 |
| `available_choices` | JSON | 是 | `skip`、`generate_asset_only`、`approve_for_future_execution` |
| `choice` | String(50) | 是 | `pending` / `skip` / `generate_asset_only` / `approve_for_future_execution` |
| `comment` | Text | 否 | 用户备注 |
| `choice_updated_at` | DateTime(timezone=True) | 否 | 选择更新时间 |
| `created_at` | DateTime(timezone=True) | 是 | 创建时间 |
| `updated_at` | DateTime(timezone=True) | 是 | 更新时间 |

规则：

- `forbidden` 和 `out_of_scope` 项不能生成可选确认项，只能作为只读 risk item。
- `approve_for_future_execution` 在 Phase 1 只是“未来可执行意向”，不能触发执行。
- PATCH 单项后，service 重新计算 plan review 状态；所有必填复核项都不再是 `pending` 时，plan 才进入 `review_saved`。

### 4.4 `scan_campaign_asset_drafts`

保存由 plan 和人工选择生成的资产草稿。它不是正式测试资产表。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | String(50) | 是 | `DRAFT-` 前缀字符串 ID |
| `campaign_id` | String(50) FK | 是 | 关联 Campaign |
| `plan_id` | String(50) FK | 是 | 关联 plan |
| `asset_type` | String(50) | 是 | `api_case_ir_step` / `visual_ui_case` |
| `source_type` | String(50) | 是 | `api_asset` / `network_observed` / `existing_test_case` / `ai_inferred` / `ai_generated` |
| `source_item_id` | String(100) | 是 | candidate 或 flow ID |
| `policy` | String(50) | 是 | 生成草稿时的策略 |
| `risk_level` | String(50) | 否 | low/medium/high |
| `draft_payload` | JSON | 是 | API Case IR v2 step 或 Visual UI case draft |
| `metadata` | JSON | 是 | source_ref、risk_reason、conditions、execution_allowed_in_phase=false |
| `skipped_reason` | Text | 否 | 未生成 draft 的原因，保留审计 |
| `created_at` | DateTime(timezone=True) | 是 | 创建时间 |

规则：

- 所有 `draft_payload.metadata.execution_allowed_in_phase` 必须是 `false`。
- `policy=forbidden`、`policy=out_of_scope` 不生成可执行 step，只能写入 skipped 结果。
- `source=ai_inferred` 且 `confidence < 0.7` 不生成 step。
- 条件允许但条件未全部通过，不生成 step。
- 生成草稿不写入 `test_cases` 或 `visual_use_cases`。

## 5. 枚举设计

### 5.1 Campaign status

| status | 含义 | 允许更新 Campaign 输入 |
|---|---|---|
| `draft` | 只保存用户输入，尚未生成 plan | 是 |
| `plan_generated` | 已生成最新 plan | 否，需先转 needs_revision 或重新保存为修订 |
| `needs_revision` | 用户返回修改范围或策略 | 是 |
| `archived` | 归档，不参与计划生成 | 否 |

### 5.2 Plan status

| status | 含义 |
|---|---|
| `generated` | AI plan 已生成，人工复核未完成 |
| `review_saved` | 必填复核项已保存选择 |
| `asset_drafts_generated` | 已生成资产草稿 |
| `superseded` | Campaign 重新生成 plan 后旧版本失效 |

### 5.3 Policy

沿用 Phase 1 页面设计中的枚举：

| policy | 后端处理 |
|---|---|
| `allowed` | 可进入候选计划，可生成 draft |
| `confirmation_required` | 必须生成 review item，未确认前不能生成 draft |
| `conditional_allowed` | 必须保存 conditions，全部通过后才允许生成 draft |
| `forbidden` | 只能展示风险，不生成 step，不进入可执行候选 |
| `out_of_scope` | 拦截并提示修改 Campaign，不生成 step |

## 6. Service 边界

### 6.1 `ScanCampaignService`

负责 Campaign draft CRUD 和字段约束。

方法建议：

| 方法 | 职责 |
|---|---|
| `create(data)` | 校验输入并创建 draft |
| `get(campaign_id)` | 获取 Campaign |
| `list(page, page_size, status, keyword, scan_mode)` | 分页列表 |
| `update(campaign_id, data)` | 只允许 `draft` / `needs_revision` 更新 |
| `delete(campaign_id)` | Phase 1 删除 draft、plan、review、draft payload，不影响正式资产 |
| `mark_needs_revision(campaign_id)` | 从 plan_generated 回到 needs_revision |

字段校验规则：

- `target.base_url` 的 host 必须命中 `boundaries.allowed_domains`。
- `allowed_domains` 至少 1 个，不允许 `*` 或空字符串。
- `allowed_paths` 至少 1 个，不允许空 scope 自动扫描。
- `max_pages`、`max_api_candidates`、`max_plan_steps` 必须为正数，并设置后端上限。
- `data_policy.environment_safety=production-readonly` 时，写操作必须在 plan 阶段降级为 forbidden 或 skipped draft。
- 涉及上传、导出、支付的 scope 必须带对应 `special_limits`，否则生成 plan 时进入人工复核或条件未满足。

### 6.2 `ScanCampaignPlanService`

负责生成和读取 AI plan。

方法建议：

| 方法 | 职责 |
|---|---|
| `generate_plan(campaign_id, regenerate, notes)` | 生成 plan，旧 latest plan 标记 superseded |
| `get_latest_plan(campaign_id)` | 获取当前最新 plan |
| `get_plan(campaign_id, plan_id)` | 获取指定版本 plan |
| `build_plan_response(plan)` | 合并 plan JSON 和 review items，返回前端 schema |

生成流程：

```text
1. 读取 Campaign draft。
2. 校验 allowed_domains / allowed_paths / action_policy / data_policy。
3. 固化 campaign_snapshot 到 generation_metadata。
4. 查询 API Asset，按 allowed_paths、method、语义、source 可信度生成候选。
5. 构造 AI prompt，要求只输出 plan/candidates/risk/review，不输出执行指令。
6. 后端 policy filter 二次处理 AI 输出。
7. forbidden/out_of_scope 写入 risk_items。
8. confirmation_required/conditional_allowed 写入 review_items。
9. 保存 scan_campaign_plans 和 scan_campaign_review_items。
10. 更新 campaign.status=plan_generated、campaign.ai_plan_id=plan.id。
```

关键原则：

- AI 只负责建议，后端 policy filter 才是最终裁决。
- AI 返回越界候选时，后端必须改写为 `out_of_scope` 或 `forbidden`。
- 生成 plan 不能创建 `Execution`、不能调用执行引擎。
- 生成 plan 不能自动保存正式 TestCase / VisualUseCase。

### 6.3 `ScanCampaignReviewService`

负责人工复核项选择。

方法建议：

| 方法 | 职责 |
|---|---|
| `update_review_item(campaign_id, plan_id, review_item_id, choice, comment)` | 更新单项选择 |
| `recalculate_review_status(plan_id)` | 所有必填复核项完成后更新 plan.status |

选择规则：

| choice | Phase 1 含义 |
|---|---|
| `skip` | 不生成该项资产草稿 |
| `generate_asset_only` | 可生成 API/UI draft，但不执行 |
| `approve_for_future_execution` | 保存为未来执行意向，Phase 1 仍只生成 draft |

非法选择：

- 对 `forbidden` 项提交 `approve_for_future_execution` 必须返回 400。
- 对 `out_of_scope` 项提交任何允许类选择必须返回 400。
- 不在 `available_choices` 内的 choice 必须返回 400。

### 6.4 `ScanCampaignAssetDraftService`

负责把 plan 中的候选转换为资产草稿。

方法建议：

| 方法 | 职责 |
|---|---|
| `generate_asset_drafts(campaign_id, plan_id, asset_types, include_only_approved)` | 生成 API/UI draft payload |
| `build_api_ir_step(candidate, campaign, plan, review_choice)` | API candidate -> API Case IR v2 step |
| `build_visual_ui_case(flow, campaign, plan, review_choice)` | UI flow -> Visual UI case draft |
| `build_skipped_item(item, reason)` | 记录跳过原因 |

API draft 生成规则：

- 只处理 `asset_types` 包含 `api_case_ir` 的请求。
- 保留 `source`、`source_ref`、`policy`、`risk_reason`、`conditions`。
- 调用 API Case IR v2 标准化逻辑，输出 `protocol=API-IR`、`version=2.0`、`step_type=API`。
- `metadata.source_type=scan_campaign`。
- `metadata.execution_allowed_in_phase=false`。

UI draft 生成规则：

- 只处理 `asset_types` 包含 `visual_ui_case` 的请求。
- 输出 Visual UI case draft JSON，不调用 `VisualUIService.create_case()`。
- 每个 UI step 的 metadata 保留 `policy`、`risk_level`、`requires_confirmation`。
- `metadata.execution_allowed_in_phase=false`。

## 7. 接口设计

统一前缀：`/api/v1/scan-campaigns`。

### 7.1 Campaign draft CRUD

| 方法 | 路径 | 行为 |
|---|---|---|
| `POST` | `/scan-campaigns` | 创建 Campaign draft |
| `GET` | `/scan-campaigns` | 分页查询 Campaign draft |
| `GET` | `/scan-campaigns/{campaign_id}` | 获取 Campaign 详情 |
| `PUT` | `/scan-campaigns/{campaign_id}` | 更新 Campaign draft，仅允许 draft/needs_revision |
| `DELETE` | `/scan-campaigns/{campaign_id}` | 删除 draft、plan、review、asset draft，不影响正式资产 |

列表查询参数：

| 参数 | 说明 |
|---|---|
| `page` | 页码，从 1 开始 |
| `page_size` | 每页数量，上限 100 |
| `status` | draft / plan_generated / needs_revision / archived |
| `keyword` | 名称、模块、范围模糊搜索 |
| `scan_mode` | blackbox / graybox / whitebox |

### 7.2 生成 AI plan

`POST /scan-campaigns/{campaign_id}/generate-plan`

请求：

```json
{
  "regenerate": false,
  "notes": "优先复用 API Asset"
}
```

处理规则：

- `regenerate=false` 且已有 latest plan 时，返回 409 或已有 plan，避免误覆盖。
- `regenerate=true` 时，旧 latest plan 标记为 `superseded`。
- 只生成 plan、候选项、风险项和人工复核项。
- 不执行测试。

### 7.3 获取 plan

| 方法 | 路径 | 行为 |
|---|---|---|
| `GET` | `/scan-campaigns/{campaign_id}/plan` | 获取最新 plan |
| `GET` | `/scan-campaigns/{campaign_id}/plans/{plan_id}` | 获取指定 plan |

响应必须包含：

- `summary`
- `scope_review`
- `ui_flows`
- `api_candidates`
- `risk_items`
- `manual_review_items`
- `asset_drafts`
- `coverage_summary`

### 7.4 更新人工确认项

`PATCH /scan-campaigns/{campaign_id}/plans/{plan_id}/review-items/{review_item_id}`

请求：

```json
{
  "choice": "generate_asset_only",
  "comment": "允许生成资产草稿，但暂不执行"
}
```

响应：更新后的 review item 和 plan review 状态。

### 7.5 生成资产草稿

`POST /scan-campaigns/{campaign_id}/plans/{plan_id}/generate-asset-drafts`

请求：

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

处理规则：

- `include_only_approved=true` 时，只生成 `generate_asset_only` 或 `approve_for_future_execution` 的确认项，以及不需确认的 allowed 项。
- `confirmation_required` 且仍是 `pending` 的项进入 `skipped_items`。
- forbidden/out_of_scope 永远进入 `skipped_items`。
- 所有草稿 metadata 必须写 `execution_allowed_in_phase=false`。
- 成功后 plan.status 更新为 `asset_drafts_generated`。

## 8. 后端策略过滤器

建议把策略判断做成 service 内部纯函数，AI 输出之后统一调用。

### 8.1 输入

```json
{
  "campaign": {},
  "candidate": {},
  "source": "api_asset",
  "source_ref": {},
  "match_score": 0.91
}
```

### 8.2 输出

```json
{
  "policy": "confirmation_required",
  "risk_level": "medium",
  "risk_reason": "会写入 test_user_* 数据",
  "conditions": [
    {"name": "环境非生产", "status": "passed", "detail": "staging"}
  ],
  "can_generate_draft": true,
  "blocked_reason": null
}
```

### 8.3 基础规则

| 条件 | policy |
|---|---|
| 域名不在 allowed_domains | `out_of_scope` |
| 路径不在 allowed_paths | `out_of_scope` |
| DELETE / 真实支付 / 发短信 / 发邮件 / 权限变更 | `forbidden` |
| POST/PUT/PATCH/DELETE 且环境非 production-readonly | `confirmation_required` |
| 上传、导出、支付 mock | `conditional_allowed` |
| GET/HEAD/OPTIONS 且无副作用 | `allowed` |
| source=`ai_inferred` 且 confidence < 0.7 | `out_of_scope` 或只展示 |

## 9. 安全和审计边界

必须保留的后端硬约束：

- `generate-plan` 不得调用执行引擎。
- `generate-asset-drafts` 不得创建 Execution。
- `generate-asset-drafts` 不得写正式 TestCase / VisualUseCase。
- `forbidden` 项不能被人工选择升级为允许。
- `out_of_scope` 项只能通过修改 Campaign scope 后重新生成 plan。
- 所有 API/UI draft 都必须带 `execution_allowed_in_phase=false`。
- AI 输出不能绕过后端 policy filter。
- Deep / whitebox 模式在 Phase 1 只能影响计划粒度，不能扩大执行能力。

审计字段建议：

| 位置 | 字段 |
|---|---|
| plan.generation_metadata | `campaign_snapshot`、`ai_provider`、`model`、`prompt_version`、`source_counts` |
| review item | `choice`、`comment`、`choice_updated_at` |
| asset draft metadata | `campaign_id`、`plan_id`、`candidate_id`、`source_ref`、`policy`、`risk_reason`、`conditions` |

## 10. 最小实现顺序

1. 新增 ORM 模型和枚举，更新 `models/__init__.py`。
2. 新增 Pydantic schema。
3. 实现 Campaign CRUD service 和 endpoint。
4. 实现 Campaign 输入校验和状态流转。
5. 实现 plan 生成骨架：先用 deterministic policy + API Asset 匹配，AI 调用可后接。
6. 实现 review item PATCH。
7. 实现 asset draft 生成，接入 API Case IR v2 标准化。
8. 注册 router。
9. 增加 API contract tests。

建议测试文件：

| 测试 | 覆盖 |
|---|---|
| `test_scan_campaigns_api_contract.py` | CRUD、generate-plan、review patch、generate-asset-drafts |
| `test_scan_campaign_policy_rules.py` | forbidden/out_of_scope/confirmation/conditional 策略 |
| `test_scan_campaign_asset_drafts.py` | API IR v2 metadata 和 execution_allowed_in_phase=false |

## 11. Phase 1 验收标准

- Campaign draft 可以创建、查询、更新、删除。
- base_url、allowed_domains、allowed_paths 的边界校验生效。
- generate-plan 返回 plan，但不产生 Execution。
- API Asset 候选能保留 source_ref 和 match reasons。
- forbidden/out_of_scope 不能生成 step。
- confirmation_required 必须生成 review item。
- review item choice 可保存且可审计。
- generate-asset-drafts 只返回/保存草稿 payload，不写正式资产表。
- 所有草稿都带 `execution_allowed_in_phase=false`。
- 后端没有 `/execute`、`/run`、`/schedule`、`/crawl-all`、`/attack-scan` 接口。
