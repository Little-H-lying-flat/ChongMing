"""
Right Pupil Engine (The Orchestrator)
右瞳引擎主编排器

集成视觉感知、规划和执行能力，实现端到端的 UI 自动化。
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

from app.engines.vision.omni_client import OmniClient
from app.engines.vision.smart_waiter import SmartWaiter
from app.engines.vision.som_renderer import SoMRenderer
from app.engines.vision.dom_service import DomService
from .planner import VisualPlanner
from app.engines.runner.ui_runner import UiRunner
from app.engines.turbo.synthesizer import DataSynthesizer
from app.schemas.execution import AUIIR
from .state import AgentState
from .graph import create_right_pupil_graph

logger = logging.getLogger(__name__)

class RightPupilEngine:
    """
    右瞳引擎 (Visual-First UI Automation Engine)
    """
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None, omni_url: str = ""):
        # 初始化核心组件
        self.omni_client = OmniClient(base_url=omni_url, client=http_client)
        self.som_renderer = SoMRenderer()
        self.dom_service = DomService()
        self.planner = VisualPlanner()
        self.data_synthesizer = DataSynthesizer()
        self.max_steps = 10
        self.waiter: Optional[SmartWaiter] = None
        
        # Initialize LangGraph
        self.graph = create_right_pupil_graph(self)


    async def start_session(self, headless: bool = True):
        """Start a browser session"""
        if hasattr(self, 'browser') and self.browser:
            return

        self.playwright = await async_playwright().start()
        # 注入防检测参数
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="local_runtime/traces/videos",
            # 伪装 User-Agent
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        
        # 应用潜行魔法
        await Stealth().apply_stealth_async(self.page)
        logger.info("🥷 Stealth Mode Activated")
        
        # Initialize Runner with the new page
        self.runner = UiRunner(self.page, self.dom_service)
        self.waiter = SmartWaiter(self.page)
        logger.info("RightPupil Session Started")

    async def stop_session(self):
        """Stop the browser session"""
        try:
            if hasattr(self, 'context') and self.context:
                await self.context.close()
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error stopping RightPupil session: {e}")
        finally:
            self.context = None
            self.browser = None
            self.playwright = None
            self.runner = None
            logger.info("RightPupil Session Stopped")

    # ═══════════════════════════════════════════
    # Task-Aware Action Correction (Layer 1)
    # ═══════════════════════════════════════════
    _INPUT_KEYWORDS = re.compile(r'输入|填写|键入|type|搜索框中|在.*框.*中.*输入|在.*中.*填', re.IGNORECASE)
    _TEXT_EXTRACT = re.compile(r"['‘’“”\"](.+?)['‘’“”\"]")  # 提取引号内的文本

    def _correct_action_type(self, action, step_description: str):
        """
        任务感知动作修正：
        如果步骤描述包含"输入/填写"等关键词，但 AI 返回了 click，则修正为 type。
        同时从描述中提取要输入的文本填入 params.text。
        """
        if not action or not step_description:
            return action
        
        if action.action_type == "click" and self._INPUT_KEYWORDS.search(step_description):
            logger.warning(
                f"🔧 Action correction: click → type (description contains input keywords: '{step_description[:60]}')"
            )
            action.action_type = "type"
            
            # 如果 params 中没有 text，尝试从描述中提取引号内容
            if not action.params.get("text"):
                match = self._TEXT_EXTRACT.search(step_description)
                if match:
                    action.params["text"] = match.group(1)
                    logger.info(f"   Extracted text from description: '{match.group(1)}'")
        
        return action

    async def execute(self, action: AUIIR) -> Any:
        """
        Execute a single UI action (Step-by-Step mode for Dispatcher)
        """
        if not hasattr(self, 'runner') or not self.runner:
            raise RuntimeError("Session not started. Call start_session() first.")

        try:
            success = await self.runner.execute(action, id_map={})
            
            strategy_name = "unknown"
            if action.target:
                strategy_name = action.target.strategy
            
            # 截取执行后的页面快照
            screenshot_b64 = None
            if hasattr(self, 'page') and self.page:
                try:
                    import base64
                    screenshot_bytes = await self.page.screenshot(type="png", full_page=True)
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                except Exception as e:
                    logger.warning(f"截图失败: {e}")
                
            res = type('Result', (object,), {
                "success": success,
                "strategy_used": type('Strategy', (object,), {"value": strategy_name})(),
                "screenshot_after": screenshot_b64,
                "error": None if success else "Execution failed"
            })()
            return res
        except Exception as e:
            logger.error(f"RightPupil Execute Error: {e}")
            return type('Result', (object,), {
                "success": False,
                "strategy_used": None,
                "screenshot_after": None,
                "error": str(e)
            })()

    # ═══════════════════════════════════════════
    # LangGraph Nodes Implementation
    # ═══════════════════════════════════════════
    
    async def node_perceive(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 感知锚定: 获取截图并调用 OmniParser
        """
        logger.info("--- [Node: Perceive] ---")
        import base64
        
        # Step 1: Wait & Screenshot
        if self.waiter:
            await self.waiter.wait_until_stable()
            
        screenshot_bytes = await self.page.screenshot(type="png")
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        # Initialize state updates
        updates = {
            "current_screenshot": screenshot_b64,
            "error": None,
            "failure_type": None
        }
        
        # Check if navigating
        if state.get("action_intent") and getattr(state["action_intent"], "action_type", "") == "navigate":
            # Just navigated, return screenshot, no need for OmniParser this cycle until next reasoned action
            return updates

        # Step 2: Perception (OmniParser -> SoM)
        try:
            elements = await self.omni_client.parse_screenshot(screenshot_b64)
            if not elements:
                logger.warning("OmniParser found no elements.")
                updates["error"] = "No elements found on screen."
                updates["failure_type"] = "VISION_FAILED"
                return updates
                
            loop = asyncio.get_running_loop()
            annotated_b64, id_map = await loop.run_in_executor(
                None, self.som_renderer.draw_som, screenshot_b64, elements
            )
            
            # Construct SoM text for the Reason node
            som_text_lines = []
            for k, v in id_map.items():
                bbox = v.get('bbox', [0, 0, 0, 0])
                w = int(bbox[2] - bbox[0])
                h = int(bbox[3] - bbox[1])
                som_text_lines.append(f"ID {k}: [{w}x{h}] {v.get('label')} {v.get('content', '')}")
            som_text = "\n".join(som_text_lines)
            
            # Live trace broadcast (Optional)
            execution_id = state.get("execution_id")
            if execution_id:
                from app.api.v1.endpoints.visual_ui import visual_ws_manager
                try:
                    asyncio.create_task(
                        visual_ws_manager.broadcast_to_execution(
                            execution_id,
                            {
                                "event": "live_trace",
                                "step_description": state.get("task_description", ""),
                                "image_b64": f"data:image/png;base64,{annotated_b64}"
                            }
                        )
                    )
                except Exception as e:
                    pass
            
            updates.update({
                "annotated_screenshot": annotated_b64,
                "id_map": id_map,
                "som_text": som_text
            })
            
        except Exception as e:
            logger.error(f"Perception failed: {e}")
            updates["error"] = f"Perception Error: {str(e)}"
            updates["failure_type"] = "VISION_FAILED"
            
        return updates

    async def node_reason(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 群智决策: AutoGen GroupChat (VisualExpert + Persona + Critic)

        """
        logger.info("--- [Node: Reason] ---")
        
        # If perceive failed, skip reasoning
        if state.get("error"):
            return {}
            
        task_desc = state.get("task_description")
        
        # Handle Navigation specifically if initial step has url but no intent yet
        if state.get("task_url") and not state.get("action_intent"):
             # For Phase 1, if we have a URL initially, we navigate first
             from app.schemas.execution import AUIIR
             action = AUIIR(
                 action_type="navigate",
                 target=type('ActionTarget', (object,), {"strategy": "url", "value": state["task_url"]})(),
                 params={}
             )
             return {"action_intent": action}
        
        try:
            from app.engines.right_pupil.agents.visual_expert import VisualExpertAgent
            from app.engines.right_pupil.agents.persona import PersonaAgent
            from app.engines.right_pupil.agents.critic import CriticAgent
            import autogen
            import json
            import re
            from app.core.config import settings
            from app.schemas.execution import AUIIR
            from app.core.ai_models import AIModule
            from app.core.ai_client import get_ai_manager
            
            # Setup AutoGen LLM Config using DashScope through our unify config
            # (In a real production setup, we'd wire AIClient in, but AutoGen expects OpenAI-compatible config dict)
            from app.services.smart_ops.ai_config_service import AIConfigService
            from app.core.ai_models import AIModule
            
            visual_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_VISUAL)
            persona_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_PERSONA)
            critic_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_CRITIC)

            def build_cfg(cfg):
                return {
                    "config_list": [{
                        "model": cfg.model_id,
                        "api_key": settings.QWEN_API_KEY,
                        "base_url": settings.QWEN_BASE_URL
                    }],
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "timeout": 120,
                }
            
            # 1. Initialize Agents
            admin = autogen.UserProxyAgent(
                name="Orchestrator",
                system_message="You manage the reasoning flow. Provide the SoM data and task to the experts. Wait for the Critic to say TERMINATE.",
                human_input_mode="NEVER",
                code_execution_config=False
            )
            
            visual_expert = VisualExpertAgent("视觉交互专家_VisualExpert", build_cfg(visual_cfg))
            persona = PersonaAgent("视觉意图拆解_Persona", build_cfg(persona_cfg))
            critic = CriticAgent("视觉审查官_Critic", build_cfg(critic_cfg))
            
            from app.engines.right_pupil.agents.librarian import search_knowledge_base
            autogen.agentchat.register_function(
                search_knowledge_base,
                caller=visual_expert,
                executor=admin,
                name="search_knowledge_base",
                description="Search the knowledge base for historical context or element locators."
            )
            autogen.agentchat.register_function(
                search_knowledge_base,
                caller=persona,
                executor=admin,
                name="search_knowledge_base",
                description="Search the knowledge base for historical context or synthetic test data examples."
            )
            
            # 2. Build GroupChat
            groupchat = autogen.GroupChat(
                agents=[admin, visual_expert, persona, critic],
                messages=[],
                max_round=10,
                speaker_selection_method="round_robin", # Admin -> Visual -> Persona -> Critic
                allow_repeat_speaker=False
            )
            
            manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=build_cfg(critic_cfg))
            
            # 3. Construct Prompt
            prompt = f"""Task: {task_desc}
            
Recent History: {json.dumps(state.get('history')[-3:] if state.get('history') else [])}

OmniParser SoM Elements:
{state.get('som_text', '')}

Please propose the next action."""

            # 4. Run GroupChat (Synchronously in executor to not block async loop)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                admin.initiate_chat,
                manager,
                prompt
            )

            # 5. Extract JSON from Critic's last message
            last_msg = None
            # Find the last message from Critic
            for msg in reversed(groupchat.messages):
                if msg.get("name") == "视觉审查官_Critic":
                    last_msg = msg.get("content", "")
                    break
                    
            if not last_msg:
                raise ValueError("Critic did not provide a final output.")
                
            # Extract JSON block
            import re
            json_str = last_msg
            json_match = re.search(r'```(?:json)?\n(.*?)\n```', last_msg, re.DOTALL)
            if json_match:
               json_str = json_match.group(1)
            else:
               # Try to find { ... }
               match = re.search(r'(\{.*\})', last_msg, re.DOTALL)
               if match:
                   json_str = match.group(1)

            action_data = json.loads(json_str)
            
            # Parse into AUIIR
            action = AUIIR(**action_data)
            
            # Action correction (fallback to our heuristics if needed)
            if action and action.action_type != "done":
                action = self._correct_action_type(action, task_desc)
                
            return {"action_intent": action}
            
        except Exception as e:
            logger.error(f"Reasoning failed (AutoGen): {e}")
            return {
                "error": f"Reasoning Error: {str(e)}",
                "failure_type": "PLANNING_FAILED"
            }

    async def node_act(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 物理执行: 使用 Playwright 执行动作
        """
        logger.info("--- [Node: Act] ---")
        
        if state.get("error"):
            return {}
            
        action = state.get("action_intent")
        if not action:
            return {"error": "No action to execute", "failure_type": "EXECUTION_FAILED"}
            
        if action.action_type == "done":
            return {"action_result": {"success": True, "details": "Task marked as done by planner"}}
            
        # Execute
        try:
            if action.action_type == "navigate":
                 await self.page.goto(action.target.value, wait_until="domcontentloaded", timeout=30000)
                 success = True
            else:
                 success = await self.runner.execute(action, state.get("id_map", {}))
            
            return {
                "action_result": {
                    "success": success,
                    "action_type": action.action_type,
                    "target": action.target.value if hasattr(action.target, 'value') else None
                }
            }
        except Exception as e:
            logger.error(f"Action Execution failed: {e}")
            return {
                "error": f"Execution Error: {str(e)}",
                "failure_type": "EXECUTION_FAILED"
            }

    async def node_evaluate(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 结果裁定: 判断动作是否成功
        """
        logger.info("--- [Node: Evaluate] ---")
        # Phase 1: Simple evaluation based on runner success boolean
        action_result = state.get("action_result", {})
        
        # If already errored out upstream
        if state.get("error"):
             return {}
             
        if not action_result.get("success", False):
             return {
                 "error": "Action execution failed in runner",
                 "failure_type": "RETRYABLE"
             }
             
        # Record history on success
        history = state.get("history", [])
        if state.get("action_intent"):
            # safely convert action to dict if model_dump is available
            intent = state["action_intent"]
            intent_dict = intent.model_dump() if hasattr(intent, 'model_dump') else str(intent)
            history.append({
                "action": intent_dict,
                "status": "success",
                "timestamp": __import__('time').time()
            })
            
        return {"history": history, "error": None, "failure_type": "NONE"}

    async def node_sherlock(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 根因分析: Call Sherlock to analyze the failure.
        """
        logger.info("--- [Node: Sherlock] ---")
        
        try:
            import autogen, json, re
            from app.engines.right_pupil.agents.sherlock import SherlockAgent
            from app.core.config import settings
            
            from app.services.smart_ops.ai_config_service import AIConfigService
            from app.core.ai_models import AIModule
            
            cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_SHERLOCK)
            llm_config = {
                "config_list": [{
                    "model": cfg.model_id,
                    "api_key": settings.QWEN_API_KEY,
                    "base_url": settings.QWEN_BASE_URL
                }],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            }
            sherlock = SherlockAgent("DOM推断专家_Sherlock", llm_config)
            admin = autogen.UserProxyAgent(
                "Admin",
                human_input_mode="NEVER",
                code_execution_config=False,
                max_consecutive_auto_reply=1
            )
            
            from app.engines.right_pupil.agents.librarian import search_knowledge_base
            autogen.agentchat.register_function(
                search_knowledge_base,
                caller=sherlock,
                executor=admin,
                name="search_knowledge_base",
                description="Search the knowledge base for root cause of known errors, system bugs, or UI changes."
            )
            
            error_msg = state.get("error", "Unknown error")
            history = state.get("history", [])
            last_action = history[-1] if history else {}
            
            prompt = f"Error: {error_msg}\nLast Action: {json.dumps(last_action)}\nAnalyze the root cause and output strict JSON."
            
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                admin.initiate_chat,
                sherlock,
                prompt
            )
            
            # Extract last reply from sherlock
            last_msg = None
            for msg in reversed(admin.chat_messages[sherlock]):
                if msg.get("role") == "assistant": # Sherlock's reply
                    last_msg = msg.get("content", "")
                    break
                    
            if not last_msg:
                last_msg = sherlock.last_message().get("content", "")
                
            json_match = re.search(r'```(?:json)?\n(.*?)\n```', last_msg, re.DOTALL)
            json_str = json_match.group(1) if json_match else last_msg
            match = re.search(r'(\{.*\})', json_str, re.DOTALL)
            if match:
                json_str = match.group(1)
                
            res = json.loads(json_str)
            failure_type = res.get("failure_type", "UNKNOWN_ERROR")
            logger.info(f"Sherlock Diagnosis: {failure_type} ({res.get('reasoning', '')})")
            
            # Scribe: Save Memory of the Diagnosis
            from app.core.memory_base import memory_base
            memory_base.add_memory(
                content=f"UI 缺陷诊断特征库: 遇到报错 {error_msg} 时，诊断根因为 {failure_type}。推理逻辑: {res.get('reasoning', '')}",
                user_id=state.get("execution_id", "default_execution_user"),
                project_id="default_proj"
            )
            
            return {"failure_type": failure_type}
            
        except Exception as e:
            logger.error(f"Sherlock failed: {e}")
            return {"failure_type": "UNKNOWN_ERROR"}

    async def node_healer(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 自愈修正: Call Healer to propose a fix based on Sherlock's RCA.
        """
        logger.info("--- [Node: Healer] ---")
        current_retries = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 1)
        
        if current_retries >= max_retries:
            logger.warning("Max retries reached. Aborting.")
            # Set failure_type to NONE so the edge defaults to END, stopping the loop
            return {"error": f"Max retries ({max_retries}) reached", "failure_type": "ABORT"}
            
        try:
            import autogen, json, re
            from app.engines.right_pupil.agents.healer import HealerAgent
            from app.schemas.execution import AUIIR
            from app.core.config import settings
            
            from app.services.smart_ops.ai_config_service import AIConfigService
            from app.core.ai_models import AIModule
            
            cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_HEALER)
            llm_config = {
                "config_list": [{
                    "model": cfg.model_id,
                    "api_key": settings.QWEN_API_KEY,
                    "base_url": settings.QWEN_BASE_URL
                }],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            }
            healer = HealerAgent("交互纠偏师_Healer", llm_config)
            admin = autogen.UserProxyAgent(
                "Admin",
                human_input_mode="NEVER",
                code_execution_config=False,
                max_consecutive_auto_reply=1
            )
            
            from app.engines.right_pupil.agents.librarian import search_knowledge_base
            autogen.agentchat.register_function(
                search_knowledge_base,
                caller=healer,
                executor=admin,
                name="search_knowledge_base",
                description="Search the knowledge base for historical state fixes, known environment issues, and recovery paths."
            )
            
            failure_type = state.get("failure_type", "UNKNOWN_ERROR")
            history = state.get("history", [])
            last_action = history[-1] if history else {}
            som_text = state.get("som_text", "")
            
            prompt = f"Failure Type: {failure_type}\nLast Action: {json.dumps(last_action)}\nCurrent SoM:\n{som_text}\nPlease propose a fixing action in strict JSON."
            
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                admin.initiate_chat,
                healer,
                prompt
            )
            
            # Extract last reply from healer
            last_msg = None
            for msg in reversed(admin.chat_messages[healer]):
                if msg.get("role") == "assistant":
                    last_msg = msg.get("content", "")
                    break
                    
            if not last_msg:
                last_msg = healer.last_message().get("content", "")
                
            json_match = re.search(r'```(?:json)?\n(.*?)\n```', last_msg, re.DOTALL)
            json_str = json_match.group(1) if json_match else last_msg
            match = re.search(r'(\{.*\})', json_str, re.DOTALL)
            if match:
                json_str = match.group(1)
                
            res = json.loads(json_str)
            if res.get("action_type") == "abort":
                return {"retry_count": current_retries + 1, "error": "Healer aborted", "failure_type": "ABORT"}
                
            action = AUIIR(**res)
            logger.info(f"Healer proposed fix: {action.action_type}")
            
            # Scribe: Save Memory of the Fix
            from app.core.memory_base import memory_base
            memory_base.add_memory(
                content=f"UI 自愈成功经验: 当遭遇 {failure_type} 且任务为 {state.get('task_description')} 时，成功使用了动作: {json.dumps(res, ensure_ascii=False)}",
                user_id=state.get("execution_id", "default_execution_user"), 
                project_id="default_proj" 
            )
            
            # Update state: clear error and failure type to allow a clean retry of node_act
            # We don't go back to node_reason; the Healer outputs the new action bypass.
            return {
                "retry_count": current_retries + 1,
                "action_intent": action,
                "error": None,
                "failure_type": None
            }
            
        except Exception as e:
            logger.error(f"Healer failed: {e}")
            return {"retry_count": current_retries + 1, "error": f"Healer error: {e}", "failure_type": "ABORT"}


    async def execute_step(self, description: str, url: str = None, execution_id: str = None) -> Dict[str, Any]:
        """
        单步 AI 执行 — Dispatcher 调用入口 (Refactored to LangGraph)
        
        将自然语言描述交给 AI Agent 执行。基于 LangGraph 的状态机完成感知、决策、执行与自愈。
        """
        if not hasattr(self, 'page') or not self.page:
            raise RuntimeError("Session not started. Call start_session() first.")
            
        logger.info(f"🔄 [execute_step] Starting LangGraph for: {description}")
        
        # 1. Initialize State
        initial_state: AgentState = {
            "task_description": description,
            "task_url": url,
            "execution_id": execution_id,
            "history": [],
            "current_screenshot": None,
            "current_dom": None,
            "som_text": None,
            "annotated_screenshot": None,
            "id_map": {},
            "action_intent": None,
            "action_result": None,
            "error": None,
            "failure_type": None,
            "retry_count": 0,
            "max_retries": 1
        }
        
        try:
            # 2. Invoke Graph (Async)
            final_state = await self.graph.ainvoke(initial_state)
            
            # 3. Format Result for Dispatcher
            success = False
            action_taken = None
            target_description = None
            
            history = final_state.get("history", [])
            if history:
                last_action = history[-1]
                if last_action.get("status") == "success":
                    success = True
                    act_intent = last_action.get("action", {})
                    if isinstance(act_intent, dict):
                        action_taken = act_intent.get("action_type")
                        target_dict = act_intent.get("target", {})
                        if isinstance(target_dict, dict):
                            target_description = target_dict.get("value")
                    else:
                        # Fallback for raw object
                        action_taken = getattr(act_intent, "action_type", "unknown")
                        
            # If navigate was successful directly targeting url (early exit from perceive / reason)
            if not success and final_state.get("action_intent"):
                intent = final_state["action_intent"]
                if getattr(intent, "action_type", "") == "navigate":
                    success = True
                    action_taken = "navigate"
                    target_description = url
                    
            # Did it hit evaluating error?
            error_msg = final_state.get("error")
            
            return {
                "success": success,
                "action_taken": action_taken,
                "target_description": target_description,
                "screenshot_before": final_state.get("current_screenshot"),
                "screenshot_after": final_state.get("annotated_screenshot") or final_state.get("current_screenshot"),
                "page_url": self.page.url,
                "page_title": await self.page.title(),
                "strategy": "ag_langgraph",
                "error": error_msg
            }
            
        except Exception as e:
            logger.error(f"❌ [execute_step] Graph Execution Error: {e}")
            import base64
            err_b64 = None
            try:
                err_bytes = await self.page.screenshot(type="png")
                err_b64 = base64.b64encode(err_bytes).decode("utf-8")
            except:
                pass
                
            return {
                "success": False,
                "error": str(e),
                "strategy": "ag_langgraph",
                "page_url": self.page.url,
                "screenshot_after": err_b64
            }


    async def run_task(self, prompt: str, url: str) -> List[Dict[str, Any]]:
        """
        Execute automation task (Autonomous Agent Mode)
        """
        logger.info(f"🚀 RightPupil Engine Starting Task: {prompt} on {url}")
        
        await self.start_session(headless=False)
        
        history: List[Dict] = []
        
        try:
            # Navigate
            logger.info(f"Navigate to {url}")
            await self.page.goto(url)
            # await self.page.wait_for_load_state("networkidle") # Replaced by SmartWait loop
            
            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                logger.info(f"--- Step {step_count}/{self.max_steps} ---")
                
                # 0. Smart Wait (Visual + Network Stability)
                if self.waiter:
                    await self.waiter.wait_until_stable()
                
                # 1. Sensing (Screenshot -> Omni -> SoM)
                screenshot_bytes = await self.page.screenshot(type="png")
                import base64
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                
                try:
                    elements = await self.omni_client.parse_screenshot(screenshot_base64)
                except Exception as e:
                    logger.error(f"OmniParser failed: {e}")
                    break

                loop = asyncio.get_running_loop()
                annotated_base64, id_map = await loop.run_in_executor(
                    None, self.som_renderer.draw_som, screenshot_base64, elements
                )
                
                # Debug: Save annotated screenshot
                try:
                    import os
                    import time
                    debug_dir = os.path.join("local_runtime", "traces", "screenshots")
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = int(time.time())
                    filename = f"step_{step_count}_{timestamp}.png"
                    filepath = os.path.join(debug_dir, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(annotated_base64))
                    logger.info(f"Saved debug screenshot to {filepath}")
                except Exception as e:
                    logger.error(f"Failed to save debug screenshot: {e}")
                
                # ... (Construct SoM Text) ...
                som_text_lines = []
                for k, v in id_map.items():
                    bbox = v.get('bbox', [0, 0, 0, 0])
                    w = int(bbox[2] - bbox[0])
                    h = int(bbox[3] - bbox[1])
                    som_text_lines.append(f"ID {k}: [{w}x{h}] {v.get('label')} {v.get('content', '')}")
                som_text = "\n".join(som_text_lines)
                
                # 2. Planning
                action = await self.planner.plan_next_step(prompt, annotated_base64, som_text, history)
                
                # 2.1 Task-aware action correction
                if action and action.action_type != "done":
                    action = self._correct_action_type(action, prompt)
                
                if not action:
                    break
                    
                if action.action_type == "done":
                    break

                # 3. Execution with Self-Healing Loop
                max_retries = 1
                retry_count = 0
                step_success = False
                
                while retry_count <= max_retries:
                    success = await self.runner.execute(action, id_map)
                    
                    if success:
                        history.append({"step": step_count, "action": action.model_dump(), "status": "success"})
                        step_success = True
                        break
                    else:
                        logger.warning(f"Action failed. Attempting Self-Healing (Retry {retry_count + 1}/{max_retries + 1})...")
                        retry_count += 1
                        
                        # --- Healing Strategy 1: Environment Healing (Popup Killer) ---
                        # Check if failure might be due to popup (simplistic check: re-sense)
                        # In a real impl, we'd check error type (ElementIntercepted).
                        # Here we blindly try to find a "Close" button if action failed.
                        logger.info("🛡️ Attempting Environment Healing (Popup Killer)...")
                        
                        # Re-sense to see popup
                        screenshot_bytes_h = await self.page.screenshot(type="png")
                        import base64
                        screenshot_base64_h = base64.b64encode(screenshot_bytes_h).decode("utf-8")
                        try:
                            elements_h = await self.omni_client.parse_screenshot(screenshot_base64_h)
                            loop = asyncio.get_running_loop()
                            _, id_map_h = await loop.run_in_executor(
                                None, self.som_renderer.draw_som, screenshot_base64_h, elements_h
                            )
                            
                            # specific logic to find X / Close
                            # This is a heuristic: look for "close", "cancel", "x" in content or label
                            popup_close_id = None
                            for pid, pinfo in id_map_h.items():
                                label = pinfo.get('label', '').lower()
                                content = pinfo.get('content', '').lower()
                                if any(k in label or k in content for k in ['close', '关闭', 'cancel', '取消']):
                                     # Simple heuristic: usually popups are on top (high z-index), but Omni doesn't give z-index.
                                     # We just try clicking it.
                                     popup_close_id = pid
                                     break
                                     
                            if popup_close_id:
                                logger.info(f"Found potential popup close button: ID {popup_close_id}")
                                # Execute Close
                                close_action = action.model_copy(deep=True) # Deep copy to avoid mutating original action
                                close_action.action_type = "click"
                                close_action.target.strategy = "visual"
                                close_action.target.value = str(popup_close_id)
                                await self.runner.execute(close_action, id_map_h)
                                await asyncio.sleep(1) # Wait for popup to close
                                continue # Retry original action loop
                                
                        except Exception as e:
                            logger.error(f"Environment Healing failed: {e}")

                        # --- Healing Strategy 3: Data Healing (Input Regeneration) ---
                        if action.action_type == "type":
                            logger.info("🧪 Attempting Data Healing (Regenerate Value)...")
                            # Heuristic: use description or locator value as field name hint
                            field_hint = action.target.description or action.target.value or "input_field"
                            new_value = self.data_synthesizer.generate_value(field_hint, context="Previous input caused failure")
                            
                            logger.info(f"Regenerated value for {field_hint}: {new_value}")
                            
                            data_action = action.model_copy(deep=True)
                            data_action.params["text"] = new_value
                            success_data = await self.runner.execute(data_action, id_map)
                            
                            if success_data:
                                history.append({"step": step_count, "action": data_action.model_dump(), "status": "healed_data"})
                                step_success = True
                                break

                        # --- Healing Strategy 2: Locator Healing (Visual -> DOM Fallback) ---
                        logger.info("🩹 Attempting Locator Healing (Visual -> DOM)...")
                        # Capture fresh state for DOM analysis
                        dom_tree = await self.dom_service.get_clickable_elements(self.page)
                        fallback_action = await self.planner.plan_fallback_step(
                            task=prompt,
                            dom_tree=dom_tree,
                            screenshot_base64=screenshot_base64 # Reuse original screenshot or new?
                        )
                        
                        if fallback_action:
                            logger.info(f"Fallback Plan Generated: {fallback_action.action_type} on {fallback_action.target.value}")
                            # Execute fallback immediately (it counts as the retry attempt)
                            success_fb = await self.runner.execute(fallback_action, {}) # DOM doesn't need ID map
                            if success_fb:
                                history.append({"step": step_count, "action": fallback_action.model_dump(), "status": "healed"})
                                step_success = True
                                break
                        
                        logger.error("All healing attempts failed.")
                
                if not step_success:
                    history.append({"step": step_count, "action": action.model_dump(), "status": "failed"})
                    break
                
                # await asyncio.sleep(2) # Replaced by SmartWait loop start
                
        except Exception as e:
            logger.error(f"Engine Loop Error: {e}")
        finally:
            logs = self.runner.trace_logs if self.runner else []
            await self.stop_session()
            
        return logs
