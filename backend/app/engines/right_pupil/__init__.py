"""
Right Pupil Engine (The Orchestrator)
右瞳引擎主编排器

集成视觉感知、规划和执行能力，实现端到端的 UI 自动化。
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.engines.vision.omni_client import OmniClient
from app.engines.vision.smart_waiter import SmartWaiter
from app.engines.vision.som_renderer import SoMRenderer
from app.engines.vision.dom_service import DomService
from .planner import VisualPlanner
from app.engines.runner.ui_runner import UiRunner
from app.engines.turbo.synthesizer import DataSynthesizer
from app.schemas.execution import AUIIR

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
        
    async def start_session(self, headless: bool = True):
        """Start a browser session"""
        if hasattr(self, 'browser') and self.browser:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="local_runtime/traces/videos"
        )
        self.page = await self.context.new_page()
        
        # Initialize Runner with the new page
        self.runner = UiRunner(self.page, self.dom_service)
        self.waiter = SmartWaiter(self.page)
        logger.info("RightPupil Session Started")

    async def stop_session(self):
        """Stop the browser session"""
        if hasattr(self, 'context') and self.context:
            await self.context.close()
        if hasattr(self, 'browser') and self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright') and self.playwright:
            await self.playwright.stop()
        
        self.runner = None
        logger.info("RightPupil Session Stopped")

    async def execute(self, action: AUIIR) -> Any:
        """
        Execute a single UI action (Step-by-Step mode for Dispatcher)
        """
        if not hasattr(self, 'runner') or not self.runner:
            raise RuntimeError("Session not started. Call start_session() first.")

        # For strict execution from Dispatcher, we might not have the full SoM loop 
        # unless the Dispatcher handles it. 
        # The Dispatcher sends an AUIIR. 
        # If strategy is 'visual', we need the ID map. 
        # However, the simple Dispatcher logic (level 1) typically sends explicit selectors or point coordinates 
        # derived from a previous planning phase, OR it expects the engine to handle it.
        
        # In this Refactor, we assume the AUIIR passed from Dispatcher is "executable" 
        # (i.e. has selector or coordinates, or strategy='dom').
        # If strategy='visual', we would need to run the sensing loop here.
        
        # For now, we implement a simple execution wrapper.
        
        try:
            # We pass empty id_map for now, assuming Dispatcher sends self-contained actions
            # or we fetch fresh DOM/Visual state if needed (Scope creep? Keep it simple).
            success = await self.runner.execute(action, id_map={})
            
            strategy_name = "unknown"
            if action.target:
                strategy_name = action.target.strategy
                
            res = type('Result', (object,), {
                "success": success,
                "strategy_used": type('Strategy', (object,), {"value": strategy_name})(),
                "screenshot_after": None, # TODO: Capture if needed
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
                som_text_lines = [f"ID {k}: {v.get('label')} {v.get('content', '')}" for k, v in id_map.items()]
                som_text = "\n".join(som_text_lines)
                
                # 2. Planning
                action = await self.planner.plan_next_step(prompt, annotated_base64, som_text, history)
                
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
