import json
import logging
from typing import Optional
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

from app.core.config import settings
from app.utils.autogen_runtime import get_autogen_runtime_status

logger = logging.getLogger(__name__)

# Basic AutoGen setup using our existing OpenAI config
llm_config = {
    "config_list": [
        {
            "model": getattr(settings, "MODEL_DEFECT_ROOT_CAUSE", "qwen-max"),
            "api_key": getattr(settings, "QWEN_API_KEY", "mock"),
            "base_url": getattr(settings, "QWEN_BASE_URL", ""),
        }
    ],
    "temperature": 0.2, # Low temperature for analytical consistency
}

async def run_diagnostic_chat(error_msg: str, context: Optional[str] = None) -> str:
    """
    Executes a multi-agent diagnostic session using AutoGen to analyze a testing defect.
    Returns a JSON string containing root_cause and suggested_fix.
    """
    logger.info("[Smart Ops] Starting Joint Diagnostic Room (GroupChat)")
    autogen_status = get_autogen_runtime_status()
    if not autogen_status.available:
        logger.warning(f"[Smart Ops] Skipping diagnostic room: {autogen_status.reason}")
        return ""

    # 1. The Coordinator/Admin
    user_proxy = UserProxyAgent(
        name="Coordinator",
        system_message="A human admin organizing a diagnostic session for a testing error. You will provide the error details and expect the Chief_Diagnostician to output the final JSON and say TERMINATE.",
        code_execution_config=False,
        human_input_mode="NEVER",
    )

    # 2. Database Expert
    dba_expert = AssistantAgent(
        name="DBA_Expert",
        system_message="""You are a database expert (DBA). 
        Analyze the error for any signs of SQL syntax issues, connection timeouts, deadlocks, data constraints, or ORM mapping errors.
        If it's DB related, provide your analysis. If not, briefly state it's out of your domain.""",
        llm_config=llm_config,
    )

    # 3. Backend Expert
    backend_expert = AssistantAgent(
        name="Backend_Expert",
        system_message="""You are a senior Backend/JVM expert. 
        Analyze the error for server-side issues like StackTraces, NullPointerExceptions, OutOfMemory, HTTP 500s, or logic errors.
        Provide your insights if applicable.""",
        llm_config=llm_config,
    )

    # 4. Frontend Expert
    frontend_expert = AssistantAgent(
        name="Frontend_Expert",
        system_message="""You are an elite Frontend/UI Automation expert. 
        Analyze the error for browser-related issues such as Playwright timeouts, elements not found, stale elements, or React rendering errors.
        Provide your insights if applicable.""",
        llm_config=llm_config,
    )

    # 5. Chief Diagnostician
    chief_diagnostician = AssistantAgent(
        name="Chief_Diagnostician",
        system_message="""You are the Chief Diagnostician. Your job is to listen to the experts, synthesize their findings, and make the final diagnosis.
        Your responsibilities:
        1. Read the error message and the opinions of the DBA, Backend, and Frontend experts.
        2. Identify the single most likely root cause.
        3. Formulate a clear, actionable suggested fix.
        4. YOU MUST Output the final result strictly as a valid JSON object containing exactly two keys: 'root_cause' (string) and 'suggested_fix' (string).
        5. The contents of 'root_cause' and 'suggested_fix' MUST be entirely in Chinese (简体中文).
        6. Append the exact word 'TERMINATE' at the very end of your final JSON response to close the meeting.
        Do NOT output anything else besides the JSON and TERMINATE.""",
        llm_config=llm_config,
    )

    # Custom speaker selection logic to enforce flow
    def custom_speaker_selection(last_speaker, groupchat):
        if last_speaker == user_proxy:
            return frontend_expert
            
        elif last_speaker == frontend_expert:
            return backend_expert
            
        elif last_speaker == backend_expert:
            return dba_expert
            
        elif last_speaker == dba_expert:
            return chief_diagnostician
            
        elif last_speaker == chief_diagnostician:
            return user_proxy  # Triggers conceptual end
            
        return "auto"

    try:
        group_chat = GroupChat(
            agents=[user_proxy, frontend_expert, backend_expert, dba_expert, chief_diagnostician],
            messages=[],
            max_round=6, # Coordinator -> Frontend -> Backend -> DBA -> Chief -> TERMINATE
            speaker_selection_method=custom_speaker_selection,
        )
    except TypeError:
        logger.warning(
            "[Smart Ops] GroupChat does not support speaker_selection_method in current version; using default turn policy."
        )
        group_chat = GroupChat(
            agents=[user_proxy, frontend_expert, backend_expert, dba_expert, chief_diagnostician],
            messages=[],
            max_round=6,
        )

    manager = GroupChatManager(groupchat=group_chat, llm_config=llm_config)

    # Start the Chat
    context_str = f"\nContext/Trace:\n{context}" if context else ""
    initial_message = f"""
    【Diagnostic Request】
    A test has failed. Please analyze the following error:
    
    Error Message:
    {error_msg}
    {context_str}
    
    Order of speaking:
    1. Frontend_Expert: Check for UI/Browser automation issues.
    2. Backend_Expert: Check for Server/API issues.
    3. DBA_Expert: Check for Database issues.
    4. Chief_Diagnostician: Synthesize and output the final JSON in Chinese, then reply TERMINATE.
    """

    try:
        # Use a_initiate_chat if async supported by AutoGen version
        if hasattr(user_proxy, 'a_initiate_chat'):
            await user_proxy.a_initiate_chat(manager, message=initial_message)
        else:
             import asyncio
             loop = asyncio.get_running_loop()
             await loop.run_in_executor(None, user_proxy.initiate_chat, manager, initial_message)
    except Exception as e:
        logger.error(f"[Smart Ops] Diagnostic GroupChat failed: {e}")
        return ""

    # Extract Results
    final_output = ""
    for msg in reversed(group_chat.messages):
        if msg.get("name") == "Chief_Diagnostician":
            final_output = str(msg.get("content", ""))
            break
            
    # Clean up TERMINATE keyword
    final_output = final_output.replace("TERMINATE", "").strip()
    
    logger.info("[Smart Ops] Diagnostic GroupChat Finished. Extracted final output.")
    return final_output
