import json
import logging
import uuid
from typing import Dict, Any, List
import autogen
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

from app.core.config import settings
from app.utils.json_repair import repair_json

logger = logging.getLogger(__name__)

async def run_scenarist_group_chat(
    extracted_points: List[str], 
    target_type: str, 
    target_url: str = "",
    context: str = ""
) -> str:
    """
    Executes a multi-agent brainstorming session using AutoGen to create testing scenarios.
    Returns a unified JSON string.
    """
    from app.services.smart_ops.ai_config_service import AIConfigService
    from app.core.ai_models import AIModule
    
    logger.info(f"[AutoGen] Starting GroupChat for Target Type: {target_type}")

    # Helper to build Autogen llm_config
    def build_llm_config(model_config):
        return {
            "config_list": [{
                "model": model_config.model_id,
                "api_key": settings.QWEN_API_KEY, # In a real app, fetch from AIConfigService too
                "base_url": settings.QWEN_BASE_URL,
            }],
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
        }

    # Fetch Configs
    admin_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_ADMIN))
    finder_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_FINDER))
    ui_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_UI_EXPERT))
    api_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_API_EXPERT))
    merger_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_MERGER))

    # --- 1. Define the Agents ---

    # The Coordinator/Admin
    user_proxy = UserProxyAgent(
        name="项目向导_Admin",
        system_message="A human admin organizing a testing strategy session. You will provide the requirements and expect the 测试总架构师_Merger to output the final JSON and say TERMINATE.",
        code_execution_config=False,
        human_input_mode="NEVER",
    )

    # URL Finder Expert
    url_finder = AssistantAgent(
        name="路由分析师_Finder",
        system_message="""You are a strict Requirements Analyst. Your UNIQUE job is to find and extract the Target URL (or Base URL) from the Context INFO or PRD.
        If a URL is explicit (e.g. 'https://example.com' or 'http://localhost:3000'), declare it clearly.
        If NO URL is specified, default to 'http://localhost:3000'.
        You MUST state the Target URL clearly so the 前端架构师_UI and 后端架构师_API can use it in their scenarios.""",
        llm_config=finder_cfg,
    )

    # UI Expert (Only participates if target is UI or MIXED)
    ui_expert = AssistantAgent(
        name="前端架构师_UI",
        system_message=f"""
你是一名资深的前端自动化测试专家 (Playwright/Selenium)。

你的唯一任务：
根据 PRD 需求，设计用户界面的 E2E 测试场景步骤。

==========================
【🔴 最高强制规则 - 不可违反 🔴】
==========================

1. 系统已注入全局基础 URL：
>>> GLOBAL_BASE_URL = {target_url} <<<

2. 所有测试场景的第一个步骤：
   必须是：
   action: open_page
   url: GLOBAL_BASE_URL

3. 严禁：
   - 使用 http://localhost
   - 编造域名
   - 猜测未提供的页面路径
   - 推断未给出的元素ID、class、xpath

4. 如果 GLOBAL_BASE_URL 为空或无法确定：
   立即输出：
   ERROR_BASE_URL_MISSING
   TERMINATE
   不允许生成任何测试步骤。

==========================
【允许的 Action 白名单】
==========================

仅允许以下 UI 原语：

- open_page
- click
- input
- select
- assert_visible
- assert_text
- assert_url
- assert_element_exist

不允许创造新 action。

==========================
【生成规则】
==========================

1. 先进行内部需求拆解分析（不要输出分析过程）。
2. 只生成基于 PRD 明确存在的行为。
3. 禁止假设 UI 元素技术细节。
4. 使用语义化描述元素（例如："点击登录按钮"）。

==========================
【输出格式】
==========================

以清晰的步骤列表输出：

- 每个步骤必须编号
- 使用简体中文
- 不输出解释性语言
- 不输出 Markdown 代码块
""",
        llm_config=ui_cfg,
    )

    # API Expert (Only participates if target is API or MIXED)
    api_expert = AssistantAgent(
        name="后端架构师_API",
        system_message=f"""
你是一名资深的后端接口测试专家。

你的唯一任务：
根据 PRD 设计 API 层测试场景。

==========================
【🔴 最高强制规则 🔴】
==========================

1. 系统已注入：
>>> GLOBAL_BASE_URL = {target_url} <<<

2. 所有 Endpoint 必须：
   以 GLOBAL_BASE_URL 作为前缀进行拼接。

   正确示例：
   GLOBAL_BASE_URL + "/login"

   错误示例：
   http://test.com/login
   http://localhost/login

3. 严禁：
   - 编造域名
   - 猜测不存在的 API
   - 创建 PRD 未提及的字段

4. 如果 GLOBAL_BASE_URL 为空：
   输出：
   ERROR_BASE_URL_MISSING
   TERMINATE

==========================
【每个 API 步骤必须包含】
==========================

- method (GET/POST/PUT/DELETE)
- full_url
- 核心 payload 字段
- 明确断言：
  - Expect status code
  - Expect response key/value

==========================
【生成规则】
==========================

1. 先进行内部逻辑拆解（不要输出）。
2. 覆盖：
   - 正向流程
   - 边界值
   - 权限校验
   - 异常输入
3. 不输出任何解释文本。
4. 使用简体中文描述测试逻辑。
""",
        llm_config=api_cfg,
    )

    # Merger Architect
    merger_architect = AssistantAgent(
        name="测试总架构师_Merger",
        system_message=f"""
你是重明 (ChongMing) 平台的首席测试架构师。

==========================
【你的任务】
==========================

整合 @前端架构师_UI 和 @后端架构师_API 的测试方案，
去重、结构化，并输出标准 JSON。

==========================
【🔴 全局变量校验 🔴】
==========================

>>> GLOBAL_BASE_URL = {target_url} <<<

在生成 JSON 前，必须执行内部检查：

1. 所有 url 必须以 GLOBAL_BASE_URL 开头。
2. 不允许出现 localhost。
3. 不允许出现未知域名。
4. JSON 必须符合标准语法。
5. 不允许任何 JSON 外的文本。

如果任一条件失败，输出：

ERROR_VALIDATION_FAILED
TERMINATE

==========================
【JSON 严格规则】
==========================

1. Key 必须 snake_case 英文。
2. Value 使用简体中文（技术字段除外）。
3. 不输出 Markdown 标记（即绝对不要输出 ```json 或者 ``` 这类代码块语法）。
4. 不输出哪怕一个字的解释或废话。仅输出裸的纯合法 JSON 对象！
5. 在 JSON 对象（最后的 }}）后面马上紧接一个换行，接着输出 TERMINATE 单词从而结束对话。

==========================
【输出结构样本】
==========================

{{
  "scenarios": [
    {{
      "scenario_id": "SC_001",
      "name": "测试名称",
      "type": "UI or API",
      "priority": "P0/P1/P2",
      "description": "简体中文描述",
      "steps": [
        {{
          "step_no": 1,
          "action": "",
          "url": "",
          "method": "",
          "payload": {{}},
          "expected_result": ""
        }}
      ]
    }}
  ]
}}
TERMINATE
""",
        llm_config=merger_cfg,
    )

    # --- 2. Build the Group Chat based on target_type ---
    agents = [user_proxy, url_finder, merger_architect]
    if target_type in ("UI", "MIXED"):
        agents.append(ui_expert)
    if target_type in ("API", "MIXED"):
        agents.append(api_expert)

    # Custom speaker selection logic to enforce flow
    def custom_speaker_selection(last_speaker, groupchat):
        if last_speaker == user_proxy:
            return url_finder
            
        elif last_speaker == url_finder:
            if target_type in ("UI", "MIXED"):
                return ui_expert
            return api_expert
            
        elif last_speaker == ui_expert:
            if target_type == "MIXED":
                return api_expert
            return merger_architect
            
        elif last_speaker == api_expert:
            return merger_architect
            
        elif last_speaker == merger_architect:
            return user_proxy  # Should trigger terminate conceptually
            
        return "auto"

    group_chat = GroupChat(
        agents=agents,
        messages=[],
        max_round=7, # Admin -> URL_Finder -> UI -> API -> Merger -> TERMINATE (Leaves room for one extra round)
        speaker_selection_method=custom_speaker_selection,
    )

    manager = GroupChatManager(groupchat=group_chat, llm_config=admin_cfg)

    # --- 3. Start the Chat ---
    points_str = json.dumps(extracted_points, ensure_ascii=False)
    
    order_steps = ["1. 路由分析师_Finder: Read the Context INFO and requirements to explicitly declare the Target URL or Base URL."]
    next_idx = 2
    if target_type in ("UI", "MIXED"):
        order_steps.append(f"{next_idx}. 前端架构师_UI: Provide UI scenarios in Chinese (简体中文). The first step MUST navigate to the URL found by 路由分析师_Finder.")
        next_idx += 1
    if target_type in ("API", "MIXED"):
        order_steps.append(f"{next_idx}. 后端架构师_API: Provide API scenarios in Chinese (简体中文). Use the URL found by 路由分析师_Finder.")
        next_idx += 1
        
    order_steps.append(f"{next_idx}. 测试总架构师_Merger: Combine scenarios, remove duplicates, ensure proper JSON structure with the required 'url' properties in every step, and output the final JSON under key 'scenarios' in Chinese (简体中文), then reply TERMINATE.")
    
    order_str = "\n    ".join(order_steps)
    
    initial_message = f"""
    Context INFO: {context}
    
    Here are the extracted business requirements and test points:
    {points_str}
    
    Please brainstorm optimal test scenarios following this strict order:
    {order_str}
    """

    # Start chatting
    # AutoGen v0.2.x initiate_chat uses synchronous mode, but await a_initiate_chat is available 
    try:
        await user_proxy.a_initiate_chat(
            manager,
            message=initial_message,
        )
    except AttributeError:
        # Fallback if a_initiate_chat is not present in installed autogen version
        user_proxy.initiate_chat(manager, message=initial_message)

    # --- 4. Extract Results ---
    # Retrieve the last message sent by 测试总架构师_Merger
    final_output = ""
    for msg in reversed(group_chat.messages):
        if msg.get("name") == "测试总架构师_Merger":
            final_output = str(msg.get("content", ""))
            break
            
    # Clean up TERMINATE keyword if present
    final_output = final_output.replace("TERMINATE", "").strip()
    
    logger.info("[AutoGen] GroupChat Finished. Extracted final output.")
    return final_output
