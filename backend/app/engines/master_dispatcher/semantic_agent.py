"""
Semantic Router Agent
Analyzes ambiguous test steps and determines execution engine context.
"""
import autogen
from typing import Dict, Any
import json
from app.core.config import settings

class SemanticRouterAgent:
    """
    基于 AutoGen 的意图分析专家
    """
    def __init__(self):
        llm_config = {
            "config_list": [
                {
                    "model": getattr(settings, "QWEN_MODEL_OMNI", "qwen-vl-max"),
                    "api_key": getattr(settings, "QWEN_API_KEY", "mock"),
                    "base_url": getattr(settings, "QWEN_BASE_URL", "")
                }
            ]
        }
        
        self.agent = autogen.ConversableAgent(
            name="SemanticRouter",
            system_message="""You are the Master Dispatcher for a Test Automation System.
Your job is to classify a test step into one of two execution engines:

1. LEFT_PUPIL (API Engine): Handles HTTP requests, database queries, data setup, assertions on JSON responses.
    - Keywords: GET, POST, payload, status code, latency, headers.
    
2. RIGHT_PUPIL (UI Engine): Handles Browser interactions, visual regression, DOM manipulation.
    - Keywords: Click, verify text on screen, screenshot, CSS selector, page load.
    
Output JSON only: {"engine_type": "LEFT_PUPIL" | "RIGHT_PUPIL", "reasoning": "..."}
""",
            llm_config=llm_config,
            human_input_mode="NEVER"
        )
        self.admin = autogen.UserProxyAgent(
            "Admin", 
            human_input_mode="NEVER", 
            code_execution_config=False, 
            max_consecutive_auto_reply=1
        )

    async def analyze(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 LLM 进行分析
        Returns dict with "engine_type" and "reasoning".
        """
        import asyncio
        loop = asyncio.get_running_loop()
        
        prompt = f"Please classify this test step:\n{json.dumps(step, ensure_ascii=False)}"
        
        await loop.run_in_executor(None, self.admin.initiate_chat, self.agent, prompt)
        
        try:
            last_msg = self.admin.chat_messages[self.agent][-1]["content"]
            json_str = last_msg[last_msg.find("{"):last_msg.rfind("}")+1]
            result = json.loads(json_str)
            
            engine_type = result.get("engine_type", "UNKNOWN")
            # Enforce valid types
            if engine_type not in ["LEFT_PUPIL", "RIGHT_PUPIL"]:
                engine_type = "UNKNOWN"
            
            return {
                "engine_type": engine_type,
                "reasoning": result.get("reasoning", "")
            }
        except Exception as e:
            return {"engine_type": "UNKNOWN", "reasoning": str(e)}
