# 欢迎加入 ChongMing

## 我们如何使用 Claude

基于过去 30 天的使用记录：

工作类型分布：
  方案设计  ████████████████████  100%

常用技能与命令：
  /model  ████████████████████  每月 1 次

常用 MCP 服务器：
  暂无  ░░░░░░░░░░░░░░░░░░░░  0 次调用

## 你的设置检查清单

### 代码库
- [ ] chongming — github.com/little-h-lying-flat/chongming

### 需要启用的 MCP 服务器
- [ ] 暂无 — 过去 30 天的使用记录里没有出现 MCP 服务器。

### 需要了解的技能
- [ ] /model — 当任务需要在速度和能力之间调整时，用它切换或查看 Claude 模型。

## 团队提示

- 默认用中文沟通项目背景、方案和执行结果；代码、命令、接口字段和错误信息保持原文。
- 优先围绕当前 ChongMing 仓库工作，不把本机其它目录或个人工作区清单写进项目文档。
- 涉及 API Key、`.env`、本地数据库、执行截图和运行产物时，先确认是否已被 `.gitignore` 忽略，避免提交敏感或临时文件。
- 做功能变更时尽量先明确链路和验证标准，再用定向测试或 smoke test 证明功能可用。
- 当前重点链路包括需求解析、接口资产库、API Case IR v2、用例执行、Left Pupil/Right Pupil 执行引擎和 Smart Ops 模型治理。

## 快速开始

1. 克隆并打开 `chongming` 仓库。
2. 后端进入 `backend`，创建虚拟环境并安装开发依赖：`pip install -e ".[dev]"`。
3. 前端进入 `frontend`，安装依赖：`npm install`。
4. 启动后端：`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`。
5. 启动前端：`npm run dev`。
6. 常用校验：`pytest backend/tests tests`、`npm run lint`、`npm run build`。
7. 如果要验证接口自动化链路，可从 OpenAPI 导入 API Asset，再生成 API Case IR v2 step，放入 TestCase 或 dynamic payload 执行回归。

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
