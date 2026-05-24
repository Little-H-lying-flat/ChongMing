# UI + API 智能扫描 Phase 1.5 交互与错误提示优化计划书

## 1. 阶段定位

Phase 1.5 是 Phase 1 完成后的体验打磨阶段，不扩大功能边界。

Phase 1 已经完成“填写范围 → 生成 AI 计划 → 人工复核 → 生成资产草稿预览”的最小闭环。Phase 1.5 只解决真实 smoke 中暴露出的可用性问题：页面滚动、Tab 切换、按钮反馈、错误恢复和状态解释。

本阶段仍然坚持：
- 只生成 Campaign 计划和资产草稿。
- 不执行测试。
- 不创建正式 TestCase。
- 不创建正式 Visual UI Case。
- 不创建 Execution。
- 不出现“开始执行 / 立即运行 / 一键扫描”等执行语义入口。

## 2. 当前问题

真实点击 smoke 已验证功能闭环可用，但存在以下体验问题：

1. 页面滚动区域复杂
   - 主工作区存在纵向滚动。
   - 窄视口下内容区可能出现横向滚动。
   - Tab 在内容滚动后容易离开视口，用户需要回到顶部才能切换。

2. Tab 和按钮点击反馈不明显
   - “人工复核”“资产草稿”Tab 切换后状态变化不够醒目。
   - “保存复核选择”“生成资产草稿预览”点击后缺少明确 loading / success / failed 状态。
   - 用户难以判断按钮是否已经触发请求。

3. 状态解释不足
   - Campaign 状态、Plan 状态、Review 状态、Asset Draft 状态之间关系不够直观。
   - `approve_for_future_execution` 容易被误解为立即执行。
   - 草稿预览和正式资产之间的区别需要更强提示。

4. 错误恢复路径不足
   - 后端未启动、接口 404、Campaign 已生成计划后不可修改等场景需要更清晰提示。
   - 重复生成 plan、无 review item、无 approved item 等状态需要可读说明。

## 3. 优化目标

### 3.1 可点击性

- Tab 切换在常见桌面视口下无需横向滚动。
- 关键按钮可点击区域明确，禁用状态明确。
- 生成和保存操作必须有 loading 状态。
- 操作完成后必须有页面内状态更新和 toast 提示。

### 3.2 可理解性

- 用户能一眼知道当前处于哪个阶段：草稿 / 已生成计划 / 已保存复核 / 已生成草稿。
- 用户能理解每个动作的后果。
- 用户能明确 Phase 1.5 不会执行测试。

### 3.3 可恢复性

- 所有请求失败都要给出可执行恢复建议。
- 页面刷新后能从已有 Campaign 状态恢复到正确 Tab。
- 用户误点后不产生危险副作用。

## 4. 页面结构优化

### 4.1 顶部状态条

在 Smart Scan 页面头部增加 Campaign 状态条：

```text
Campaign: 用户管理 Smoke 灰盒扫描
状态: plan_generated
当前阶段: 2 / 4  人工复核

[1 Campaign 草稿] → [2 AI 计划] → [3 人工复核] → [4 资产草稿]
```

状态映射：

| 后端状态 | 页面阶段 | 说明 |
| --- | --- | --- |
| `draft` | Campaign 草稿 | 可编辑范围并生成计划 |
| `plan_generated` | AI 计划 / 人工复核 | 已生成计划，可保存复核选择 |
| `review_saved` | 人工复核 | 已保存至少一项复核选择 |
| `asset_drafts_generated` | 资产草稿 | 已生成资产草稿预览 |
| `needs_revision` | Campaign 草稿 | 需要修改范围后重新生成 |
| `archived` | 只读 | 不允许继续生成 |

### 4.2 Tab 区域固定化

优化规则：
- Tab List 固定在右侧主工作区顶部。
- 主内容区域内部滚动，不让 Tab 随内容滚走。
- Tab 按钮使用 `grid-cols-4` 或响应式换行，避免横向滚动。
- 在移动或窄窗口下，Tab 可变为两行：

```text
[Campaign 草稿] [AI 计划]
[人工复核]     [资产草稿]
```

### 4.3 Campaign 列表优化

Campaign 列表卡片增加：
- 状态 badge。
- 最近更新时间。
- 当前是否已有 plan。
- 当前是否已有 asset drafts。

空状态：

```text
还没有 Campaign
先创建一个扫描范围草稿，Phase 1.5 只会生成计划和草稿。
[新建 Campaign]
```

## 5. 交互状态优化

### 5.1 保存 Campaign 草稿

按钮状态：

| 场景 | 按钮文案 | 状态 |
| --- | --- | --- |
| 默认 | 保存 Campaign 草稿 | enabled |
| 请求中 | 保存中... | disabled |
| 成功 | 保存 Campaign 草稿 | enabled + toast |
| 表单不完整 | 保存 Campaign 草稿 | disabled 或点击后字段提示 |

成功提示：

```text
Campaign 草稿已保存，可继续生成 AI 计划。
```

失败提示：

```text
保存失败：请检查目标 URL、允许域名和必填字段。
```

### 5.2 生成 AI 计划

按钮状态：

| 场景 | 按钮文案 | 状态 |
| --- | --- | --- |
| 可生成 | 生成 AI 计划 | enabled |
| 请求中 | 正在生成计划... | disabled |
| 已生成且不可重复 | AI 计划已生成 | disabled |
| 允许重新生成 | 重新生成 AI 计划 | enabled，需要二次确认 |

提示文案：

```text
生成 AI 计划只会创建候选流程、API 候选和风险项，不会执行任何测试请求。
```

重复生成策略：
- 默认不允许无确认重复生成。
- 若后端支持 `regenerate=true`，前端必须弹出确认：

```text
重新生成会把当前计划标记为 superseded，并生成新版本。已保存的复核选择不会自动迁移。
```

### 5.3 保存人工复核

每个 review item 独立保存，按钮状态：

| 场景 | 按钮文案 | 状态 |
| --- | --- | --- |
| 未选择 | 保存复核选择 | disabled |
| 已选择 | 保存复核选择 | enabled |
| 请求中 | 保存中... | disabled |
| 成功 | 已保存 | 短暂显示后恢复 |

复核选择解释：

| choice | 页面文案 | 解释 |
| --- | --- | --- |
| `skip` | 跳过 | 不生成该项资产草稿 |
| `generate_asset_only` | 只生成资产草稿 | 只进入草稿预览，不执行 |
| `approve_for_future_execution` | 保存未来执行意向 | 仅记录未来意向，Phase 1.5 不执行 |

必须展示固定说明：

```text
即使选择“保存未来执行意向”，本阶段也不会执行测试。执行能力留到 Phase 3。
```

### 5.4 生成资产草稿预览

按钮状态：

| 场景 | 按钮文案 | 状态 |
| --- | --- | --- |
| 可生成 | 生成资产草稿预览 | enabled |
| 请求中 | 正在生成草稿... | disabled |
| 已生成 | 重新生成草稿预览 | enabled，需要确认 |
| 无可生成项 | 生成资产草稿预览 | disabled + 原因说明 |

成功提示：

```text
资产草稿已生成，仅用于预览；不会写入正式 API Auto 或 Visual UI 用例。
```

无可生成项提示：

```text
当前没有可生成草稿的复核项。请至少选择一项“只生成资产草稿”。
```

## 6. 错误提示规范

### 6.1 通用错误

| 错误 | 页面提示 | 恢复建议 |
| --- | --- | --- |
| 后端未启动 | 无法连接后端服务 | 检查后端是否运行，或确认 API 地址配置 |
| 404 | 当前后端不支持 Smart Scan 接口 | 请确认运行的是最新后端服务 |
| 400 | 请求内容不符合要求 | 检查必填字段和范围边界 |
| 409 | 当前状态不允许该操作 | 刷新 Campaign 状态或新建 Campaign |
| 500 | 后端处理失败 | 保留 Campaign 草稿，稍后重试 |

### 6.2 Campaign 错误

- Campaign 已生成计划后再保存草稿：

```text
当前 Campaign 已生成计划，不能直接修改范围。请新建 Campaign 或使用重新生成流程。
```

- allowed_domains 为空：

```text
请至少填写一个允许域名。Smart Scan 不会扫描未授权域名。
```

- base_url 域名不在 allowed_domains：

```text
目标 URL 的域名不在允许域名内，请确认授权范围。
```

### 6.3 Plan 错误

- 无 API Asset 匹配：

```text
没有匹配到 API Asset。仍可查看 UI 流程草稿，但 API 候选为空。建议先在 API Auto 中导入或创建接口资产。
```

- 所有 API 候选被禁止：

```text
当前 API 候选全部属于禁止或越界范围，本阶段不会生成可用草稿。
```

### 6.4 Review 错误

- 保存复核失败：

```text
复核选择保存失败。请刷新后确认该计划是否仍是最新版本。
```

- review item 不存在：

```text
该复核项已失效，可能是计划被重新生成。请刷新最新计划。
```

### 6.5 Asset Draft 错误

- 没有 approved/generate_asset_only 项：

```text
没有可生成草稿的复核项。请先在人工复核中选择“只生成资产草稿”。
```

- 草稿生成失败：

```text
资产草稿生成失败。Campaign 和复核选择已保留，可稍后重试。
```

## 7. 可访问性和基础 UX 要求

- 所有表单字段必须有可见 label。
- 所有按钮 loading 时必须 disabled。
- Toast 之外，关键状态必须在页面内可见。
- 错误信息必须说明原因和下一步。
- Tab 可通过键盘切换。
- Select 选择后焦点不应丢失到不可见区域。
- 窄屏下不出现主内容横向滚动；JSON 预览区可以独立横向滚动。

## 8. 安全边界检查

Phase 1.5 完成前必须检查：

```bash
rg "开始执行|立即运行|一键扫描|PlayCircle|/executions|/run|/schedule|left-pupil|execute" frontend/src/app/smart-scan frontend/src/services/scanCampaignService.ts frontend/src/components/Sidebar.tsx
```

允许出现的例外：
- 文档中的禁止说明。
- `approve_for_future_execution` 作为后端 choice 字段展示，但页面必须解释为“未来意向，不立即执行”。

不允许：
- 新增执行按钮。
- 调用执行接口。
- 自动保存正式资产。
- 默认把写操作标记为可执行。

## 9. 验证方式

### 9.1 手工 smoke

1. 启动最新后端和前端。
2. 打开 `/smart-scan`。
3. 新建 Campaign。
4. 保存 Campaign 草稿。
5. 生成 AI 计划。
6. 切换到人工复核。
7. 选择 `generate_asset_only`。
8. 保存复核。
9. 切换到资产草稿。
10. 生成资产草稿预览。
11. 刷新页面，确认状态能恢复。
12. 缩小浏览器宽度，确认 Tab 和按钮仍可点击。

### 9.2 错误路径 smoke

1. 后端关闭时打开页面，应显示连接失败说明。
2. 使用旧后端或错误端口，应提示接口不可用。
3. 已生成计划的 Campaign 再保存草稿，应提示状态不允许。
4. 未选择 review choice 时，保存按钮不可用。
5. 无可生成项时，资产草稿按钮不可用或显示原因。

### 9.3 退出标准

- 真实点击 smoke 一次通过，不需要 DOM 事件或精确坐标辅助。
- Tab 切换不受滚动位置影响。
- 每个异步操作都有 loading、success、error 状态。
- 用户能从页面内理解“当前不会执行”。
- 安全边界 grep 无异常。
- 刷新后可恢复当前 Campaign、Plan、Review、Asset Draft 状态。

## 10. 非目标

Phase 1.5 不做：
- 不生成正式 API Auto 用例。
- 不生成正式 Visual UI 用例。
- 不接入 Execution。
- 不做 Campaign 执行。
- 不做真实浏览器 Network 捕获。
- 不做真实 LLM planner。
- 不重构整体设计系统。

## 11. 后续衔接

Phase 1.5 完成后进入 Phase 2：资产确认生成 MVP。

Phase 2 才允许新增“确认保存为正式资产”能力，但仍不允许 Campaign 直接执行。执行能力留到 Phase 3。