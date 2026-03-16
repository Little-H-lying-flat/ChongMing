# 视觉 AI 自动化场景测试报告（2026-03-05）

## 1. 练习网站调研（联网）

- SauceDemo: https://www.saucedemo.com/
- The Internet (Herokuapp): https://the-internet.herokuapp.com/
- Test Pages (Herokuapp): https://testpages.herokuapp.com/
- ExpandTesting Practice: https://practice.expandtesting.com/login
- UI Testing Playground: https://uitestingplayground.com/

> 说明：`uitestingplayground.com` 在当前执行环境出现证书错误（`ERR_CERT_COMMON_NAME_INVALID`），未纳入本轮稳定回归。

## 2. 场景执行与结果

### 2.1 SauceDemo 登录（成功）
- 结果文件: `backend/tmp_visual_ai_eval_saucedemo_after_fix.json`
- 步骤动作: `navigate -> type -> type -> click`
- 目标验证:
  - URL 包含 `/inventory.html`
  - `.inventory_list` 存在
  - 登录错误条不存在
- 结论: 成功，返回数据与页面真实状态一致。

### 2.2 The Internet Add/Remove（成功）
- 结果文件: `backend/tmp_visual_ai_eval_the_internet_after_fix.json`
- 步骤动作: `navigate -> click`
- 目标验证:
  - `button.added-manually` 计数 > 0
- 结论: 成功，执行结果合理。

### 2.3 ExpandTesting 登录（失败样本）
- 结果文件:
  - `backend/tmp_visual_ai_eval_multi_sites_v2.json`
  - `backend/tmp_visual_ai_eval_expandtesting_after_fix_v2.json`
- 观察:
  - 存在广告/跳转干扰，出现非预期页面
  - 单步 `success=true` 与最终业务目标（进入 `/secure`）不一致
- 结论: 不满足业务成功标准，需基于“业务断言”而非仅动作成功判断。

## 3. 本轮代码修复

文件: `backend/app/engines/right_pupil/__init__.py`

1. 修复首次带 URL 步骤先感知导致 `about:blank` 失败问题
- 首步带 `task_url` 时，先跳过视觉解析，优先进入导航动作。

2. 修复 `navigate` 动作协议不一致问题
- 改为标准 `params.url` 传递导航地址；
- `node_act` 同时兼容 `params.url/target.value` 读取。

3. 修复 AutoGen 版本兼容问题
- 增加 `_register_tool_if_supported`，在缺失 `register_function` 时降级不中断。

4. 增加规划失败兜底
- AutoGen 失败时回退 `VisualPlanner.plan_next_step`，降低全链路失败率。

5. 修复结果组装误判
- `page.title()` 异常不再导致整步直接失败（保留 warning，返回空标题）。

6. 强化输入纠偏
- 扩展输入关键词（含 `username/password/email/...`）；
- 新增 `_infer_input_text`，在缺失 `params.text` 时从步骤描述自动提取输入值。

## 4. 当前已知残留问题

- AutoGen `GroupChat.__init__(speaker_selection_method=...)` 仍与当前安装版本存在兼容差异；
  当前依赖 `VisualPlanner` 兜底可执行，但链路耗时会增加。

