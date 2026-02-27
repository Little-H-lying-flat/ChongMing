import json
import logging
from typing import Dict, Any, List
import autogen
from autogen import AssistantAgent, UserProxyAgent

from app.core.config import settings

logger = logging.getLogger(__name__)

# Single Agent config for the Editor
llm_config = {
    "config_list": [
        {
            "model": getattr(settings, "MODEL_NEURAL_SCENARIO", "qwen-max"),
            "api_key": getattr(settings, "QWEN_API_KEY", "mock"),
            "base_url": getattr(settings, "QWEN_BASE_URL", ""),
        }
    ],
    "temperature": 0.1, # Extremely low temp for precise JSON editing
}

async def run_editor_agent(
    scenarios: List[Dict[str, Any]], 
    feedback: str, 
    context: str = ""
) -> str:
    """
    Executes a single AutoGen agent to precisely edit scenarios based on Critic feedback.
    Returns a unified JSON string.
    """
    logger.info("[AutoGen Editor] Starting quick correction session.")

    # Coordinator
    user_proxy = UserProxyAgent(
        name="Admin",
        system_message="A human admin submitting scenarios and critic feedback to the Editor.",
        code_execution_config=False,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1
    )

    # The dedicated JSON Editor
    editor_agent = AssistantAgent(
        name="JSON_Editor",
        system_message="""You are a precise JSON Editor and QA Specialist. 
        Your task is to take the existing list of test scenarios and the Critic's feedback, and carefully modify the JSON to fix ALL issues raised by the Critic.
        Requirements:
        1. Ensure every scenario step has a 'url' property as requested.
        2. Keep titles, descriptions, and steps in Chinese (简体中文).
        3. Do NOT invent new scenarios unless explicitly told to. Only repair the existing ones.
        4. YOU MUST Output the final result strictly as a valid JSON object with a single key 'scenarios' containing the updated list.
        5. Do NOT output markdown text outside the JSON block. Just the raw JSON.""",
        llm_config=llm_config,
    )

    scenarios_str = json.dumps(scenarios, ensure_ascii=False, indent=2)
    
    prompt = f"""
    【Context INFO】
    {context}
    
    【Existing Scenarios (JSON)】
    {scenarios_str}
    
    【CRITICAL Critic Feedback - MUST FIX】
    {feedback}
    
    Please provide the corrected JSON.
    """

    try:
        # Use a_initiate_chat if async supported, else fallback to sync
        if hasattr(user_proxy, 'a_initiate_chat'):
             import asyncio
             loop = asyncio.get_running_loop()
             await loop.run_in_executor(None, user_proxy.initiate_chat, editor_agent, prompt)
        else:
             user_proxy.initiate_chat(editor_agent, message=prompt)
    except Exception as e:
        logger.error(f"[AutoGen Editor] Failed to run editor agent: {e}")
        return ""

    # Extract Results
    try:
        last_msg = user_proxy.chat_messages[editor_agent][-1]["content"]
        # Basic JSON extraction
        json_str = last_msg[last_msg.find("{"):last_msg.rfind("}")+1]
        logger.info("[AutoGen Editor] Correction Finished. Extracted final output.")
        return json_str
    except Exception as e:
        logger.error(f"Failed to parse editor output: {e}\nRaw Message: {last_msg}")
        return ""
