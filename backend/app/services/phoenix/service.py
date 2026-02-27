from typing import Dict, Any, Optional
import json
import uuid

from loguru import logger
from app.core.ai_client import AIClientManager, get_ai_manager, AIModule, Message
from app.core.prompts.phoenix import (
    TRACE_TO_SCRIPT_SYSTEM_PROMPT, TRACE_TO_SCRIPT_USER_TEMPLATE,
    ERROR_ANALYSIS_SYSTEM_PROMPT, ERROR_ANALYSIS_USER_TEMPLATE
)
from app.utils.code_extractor import extract_code_block
from app.utils.json_repair import repair_json

class PhoenixService:
    """
    Phoenix Service (Self-Healing & Code Generation)
    """
    
    def __init__(self, ai_manager: AIClientManager):
        self.ai = ai_manager

    async def compile_trace_to_script(self, trace_data: Dict[str, Any]) -> str:
        """
        Compile execution trace to Playwright script
        """
        trace_json = json.dumps(trace_data, ensure_ascii=False, indent=2)
        
        user_content = TRACE_TO_SCRIPT_USER_TEMPLATE.format(trace_log=trace_json)
        
        messages = [
            Message(role="system", content=TRACE_TO_SCRIPT_SYSTEM_PROMPT),
            Message(role="user", content=user_content)
        ]
        
        try:
            # Generate script using LLM
            response = await self.ai.invoke(
                module=AIModule.AGENT_NEURAL_API_EXPERT,
                messages=messages
            )
            
            # Extract code block robustly
            script_content = extract_code_block(response.content, language="python")
            
            if not script_content:
                logger.warning("LLM returned no code block, using raw content")
                script_content = response.content.strip()
                
            return script_content
            
        except Exception as e:
            logger.error(f"Failed to compile trace: {e}")
            raise ValueError(f"Trace compilation failed: {e}")

    async def heal_script(self, code_snippet: str, error_log: str) -> Dict[str, Any]:
        """
        Analyze error and suggest fix
        """
        user_content = ERROR_ANALYSIS_USER_TEMPLATE.format(
            error_log=error_log,
            code_snippet=code_snippet
        )
        
        messages = [
            Message(role="system", content=ERROR_ANALYSIS_SYSTEM_PROMPT),
            Message(role="user", content=user_content)
        ]
        
        try:
            response = await self.ai.invoke(
                module=AIModule.AGENT_LEFT_SHERLOCK,
                messages=messages
            )
            
            # Parse JSON response robustly
            try:
                return repair_json(response.content)
            except Exception:
                 # Fallback if really broken
                 return {
                     "analysis": response.content,
                     "fix_code": "",
                     "reason": "LLM did not return valid JSON"
                 }
                 
        except Exception as e:
             logger.error(f"Failed to heal script: {e}")
             return {
                 "analysis": f"Internal Error: {str(e)}",
                 "fix_code": "",
                 "reason": "Service Error"
             }
