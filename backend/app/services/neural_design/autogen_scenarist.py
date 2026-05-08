import json
import logging
from typing import Any, Dict, List

import autogen
from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent

from app.core.config import settings
from app.utils.autogen_runtime import get_autogen_runtime_status


logger = logging.getLogger(__name__)


def _build_admin_system_message() -> str:
    return (
        "You are coordinating a QA scenario design session. "
        "Provide the requirements and require the final merged response to be strict JSON plus TERMINATE. "
        "Global language rule: scenario titles, scenario descriptions, step descriptions, and expected results "
        "must default to Simplified Chinese. Keep JSON keys and technical fields in English."
    )


def _build_finder_system_message() -> str:
    return """
You are a strict requirements analyst.

Your only job is to find and declare the target URL or base URL from the context or PRD.

Rules:
1. If a URL is explicitly provided, declare it clearly.
2. If no URL is specified, default to http://localhost:3000.
3. Do not design scenarios.
4. Any explanatory text should default to Simplified Chinese.
5. Keep the URL itself unchanged.
""".strip()


def _build_ui_system_message(target_url: str) -> str:
    return f"""
你是一名资深的前端自动化测试专家，负责设计可执行的 UI 测试场景。

全局约束:
1. GLOBAL_BASE_URL = {target_url}
2. 所有 UI 场景的首个导航步骤必须基于 GLOBAL_BASE_URL。
3. 不要编造域名、页面路径、元素 ID、class 或 xpath。
4. 如果 GLOBAL_BASE_URL 为空且上下文无法确定，请输出 ERROR_BASE_URL_MISSING 并 TERMINATE。

强覆盖规则:
1. 如果需求中存在编号的验收步骤、场景步骤、操作/视觉预期，必须覆盖每个显式编号步骤。
2. 如果需求描述的是连续主流程，优先生成一条端到端 happy path 场景，按需求顺序串联所有关键步骤。
3. 如果需求中写了“先登录，再添加商品，再校验购物车”等后续动作，禁止只生成登录流程后就结束。
4. 需求中明确给出的商品名、按钮文案、商品名、账号、密码、URL，必须原样保留，不要泛化或省略。
5. 对于登录后商品页、购物车、结算等后续页面动作，必须继续补齐到可执行步骤和可验证断言。

允许的 UI action:
- open_page
- click
- input
- select
- assert_visible
- assert_text
- assert_url
- assert_element_exist

输出规则:
1. 只根据需求中明确存在的行为生成场景。
2. 场景名称、场景描述、步骤描述默认必须使用简体中文。
3. 不要输出英文标题或英文步骤描述，除非是必须保留的产品名、URL、选择器或技术字段。
4. 不输出 markdown，不输出解释性废话。
""".strip()


def _build_api_system_message(target_url: str) -> str:
    return f"""
你是一名资深的后端接口测试专家，负责设计可执行的 API 测试场景。

全局约束:
1. GLOBAL_BASE_URL = {target_url}
2. 所有 endpoint 必须基于 GLOBAL_BASE_URL 拼接。
3. 不要编造域名、接口、字段或业务规则。
4. 如果 GLOBAL_BASE_URL 为空且上下文无法确定，请输出 ERROR_BASE_URL_MISSING 并 TERMINATE。

每个 API 步骤至少要包含:
- method
- full_url
- 核心 payload 字段
- 明确断言

输出规则:
1. 场景名称、场景描述、步骤描述、预期结果默认必须使用简体中文。
2. 不要输出英文标题或英文步骤描述，除非是必须保留的产品名、URL、方法名、字段名或断言路径。
3. 不输出 markdown，不输出解释性废话。
""".strip()


def _build_merger_system_message(target_url: str) -> str:
    return f"""
你是 ChongMing 平台的测试总架构师，负责合并并输出最终场景 JSON。

全局校验:
1. GLOBAL_BASE_URL = {target_url}
2. 所有 url 必须基于 GLOBAL_BASE_URL 或需求中明确给出的正式地址。
3. 不允许出现 localhost 之外的编造域名。
4. 最终输出必须是严格 JSON，并在 JSON 后单独输出 TERMINATE。

覆盖校验:
1. 不要丢弃需求中明确列出的编号步骤、验收步骤、验收标准。
2. 如果需求中的主流程包含多个连续业务动作，最终结果必须覆盖完整链路，而不是只保留第一段。
3. 如果需求里出现“登录后添加商品/加入购物车/校验购物车数字”这类后续动作，最终 happy path 场景必须保留这些动作。
4. 需求中明确给出的商品名、账号、密码、按钮文案、URL，必须原样保留。

JSON 规则:
1. Key 必须保持英文 snake_case。
2. 人类可读字段默认使用简体中文:
   - scenario.name
   - scenario.description
   - step.description
   - expected_result
3. 不要输出英文标题或英文步骤描述，除非是必须保留的产品名、URL、选择器、方法名或字段名。
4. 不输出 markdown，不输出 JSON 之外的解释文字。

输出结构:
{{
  "scenarios": [
    {{
      "scenario_id": "SC_001",
      "name": "中文测试场景名称",
      "type": "UI or API",
      "priority": "P0/P1/P2",
      "description": "中文场景描述",
      "steps": [
        {{
          "step_no": 1,
          "action": "",
          "url": "",
          "method": "",
          "payload": {{}},
          "description": "中文步骤描述",
          "expected_result": "中文预期结果"
        }}
      ]
    }}
  ]
}}
TERMINATE
""".strip()


async def run_scenarist_group_chat(
    extracted_points: List[str],
    target_type: str,
    target_url: str = "",
    context: str = "",
) -> str:
    """
    Execute a multi-agent brainstorming session using AutoGen and return the
    final merged JSON string.
    """
    from app.core.ai_models import AIModule
    from app.services.smart_ops.ai_config_service import AIConfigService

    logger.info(f"[AutoGen] Starting GroupChat for Target Type: {target_type}")
    autogen_status = get_autogen_runtime_status()
    if not autogen_status.available:
        logger.warning(f"[AutoGen] Skipping scenarist chat: {autogen_status.reason}")
        return ""

    def build_llm_config(model_config: Any) -> Dict[str, Any]:
        return {
            "config_list": [
                {
                    "model": model_config.model_id,
                    "api_key": settings.QWEN_API_KEY,
                    "base_url": settings.QWEN_BASE_URL,
                }
            ],
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
        }

    admin_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_ADMIN))
    finder_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_FINDER))
    ui_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_UI_EXPERT))
    api_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_API_EXPERT))
    merger_cfg = build_llm_config(await AIConfigService.get_model_config(AIModule.AGENT_NEURAL_MERGER))

    user_proxy = UserProxyAgent(
        name="项目向导_Admin",
        system_message=_build_admin_system_message(),
        code_execution_config=False,
        human_input_mode="NEVER",
    )

    url_finder = AssistantAgent(
        name="路由分析师_Finder",
        system_message=_build_finder_system_message(),
        llm_config=finder_cfg,
    )

    ui_expert = AssistantAgent(
        name="前端架构师_UI",
        system_message=_build_ui_system_message(target_url),
        llm_config=ui_cfg,
    )

    api_expert = AssistantAgent(
        name="后端架构师_API",
        system_message=_build_api_system_message(target_url),
        llm_config=api_cfg,
    )

    merger_architect = AssistantAgent(
        name="测试总架构师_Merger",
        system_message=_build_merger_system_message(target_url),
        llm_config=merger_cfg,
    )

    agents = [user_proxy, url_finder, merger_architect]
    if target_type in ("UI", "MIXED"):
        agents.append(ui_expert)
    if target_type in ("API", "MIXED"):
        agents.append(api_expert)

    def custom_speaker_selection(last_speaker: Any, groupchat: Any) -> Any:
        if last_speaker == user_proxy:
            return url_finder
        if last_speaker == url_finder:
            if target_type in ("UI", "MIXED"):
                return ui_expert
            return api_expert
        if last_speaker == ui_expert:
            if target_type == "MIXED":
                return api_expert
            return merger_architect
        if last_speaker == api_expert:
            return merger_architect
        if last_speaker == merger_architect:
            return user_proxy
        return "auto"

    try:
        group_chat = GroupChat(
            agents=agents,
            messages=[],
            max_round=7,
            speaker_selection_method=custom_speaker_selection,
        )
    except TypeError:
        logger.warning(
            "[AutoGen] GroupChat does not support speaker_selection_method in current version; "
            "using default turn policy."
        )
        group_chat = GroupChat(
            agents=agents,
            messages=[],
            max_round=7,
        )

    manager = GroupChatManager(groupchat=group_chat, llm_config=admin_cfg)

    points_str = json.dumps(extracted_points, ensure_ascii=False)

    order_steps = [
        "1. 路由分析师_Finder：先明确目标 URL 或基础 URL。",
    ]
    next_idx = 2
    if target_type in ("UI", "MIXED"):
        order_steps.append(
            f"{next_idx}. 前端架构师_UI：输出简体中文 UI 场景，首个导航步骤必须使用 Finder 给出的 URL。"
        )
        next_idx += 1
    if target_type in ("API", "MIXED"):
        order_steps.append(
            f"{next_idx}. 后端架构师_API：输出简体中文 API 场景，接口地址必须使用 Finder 给出的 URL。"
        )
        next_idx += 1
    order_steps.append(
        f"{next_idx}. 测试总架构师_Merger：合并去重，输出严格 JSON，"
        "并确保场景标题、场景描述、步骤描述、预期结果默认是简体中文，然后输出 TERMINATE。"
    )
    order_str = "\n".join(order_steps)

    initial_message = f"""
Context INFO:
{context}

Extracted business requirements and test points:
{points_str}

Mandatory coverage rule:
- If the requirement contains numbered acceptance steps, every numbered step must appear in at least one scenario.
- For a sequential business flow, prefer one complete happy-path scenario that preserves the original order.
- Do not stop at login if later acceptance steps describe post-login actions such as browsing products, adding to cart, or verifying badge counts.
- Preserve explicit product names, credentials, and URLs from the requirement.

Global language rule:
- Scenario titles, scenario descriptions, step descriptions, and expected results must default to Simplified Chinese.
- Keep JSON keys, selectors, URLs, HTTP methods, payload keys, and assertion paths in English when needed.
- Do not output English-only scenario titles or step descriptions unless the term must remain in English.

Please brainstorm optimal test scenarios following this strict order:
{order_str}
""".strip()

    try:
        await user_proxy.a_initiate_chat(
            manager,
            message=initial_message,
        )
    except AttributeError:
        user_proxy.initiate_chat(manager, message=initial_message)

    final_output = ""
    for msg in reversed(group_chat.messages):
        if msg.get("name") == "测试总架构师_Merger":
            final_output = str(msg.get("content", ""))
            break

    final_output = final_output.replace("TERMINATE", "").strip()
    logger.info("[AutoGen] GroupChat finished. Extracted final output.")
    return final_output
