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

    async def execute_step(self, description: str, url: str = None) -> Dict[str, Any]:
        """
        单步 AI 执行 — Dispatcher 调用入口
        
        将自然语言描述交给 AI Agent 的一次 Sense→Plan→Act 循环:
        1. (可选) 导航到 URL
        2. Smart Wait → 截图 → OmniParser → SoM
        3. VisualPlanner 根据 description 规划动作
        4. UiRunner 执行
        5. 截图 → 返回结果
        """
        import base64
        
        if not hasattr(self, 'page') or not self.page:
            raise RuntimeError("Session not started. Call start_session() first.")
        
        result = {
            "success": False,
            "action_taken": None,
            "target_description": None,
            "screenshot_before": None,
            "screenshot_after": None,
            "page_url": None,
            "page_title": None,
            "strategy": "ai_vision",
            "error": None,
        }
        
        try:
            # Step 0: 导航 (如果有 URL)
            if url:
                logger.info(f"🌐 [execute_step] 导航: {url}")
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if self.waiter:
                    await self.waiter.wait_until_stable()
                
                # 纯导航步骤直接返回成功
                screenshot_bytes = await self.page.screenshot(type="png")
                result["success"] = True
                result["action_taken"] = "navigate"
                result["target_description"] = url
                result["screenshot_after"] = base64.b64encode(screenshot_bytes).decode("utf-8")
                result["page_url"] = self.page.url
                result["page_title"] = await self.page.title()
                return result
            
            # Step 1: Smart Wait
            if self.waiter:
                await self.waiter.wait_until_stable()
            
            # Step 2: 截图 (Before)
            screenshot_bytes = await self.page.screenshot(type="png")
            screenshot_before_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            result["screenshot_before"] = screenshot_before_b64
            result["page_url"] = self.page.url
            result["page_title"] = await self.page.title()
            
            # Step 3 & 4: Perception & Planning (Visual First, DOM Fallback)
            id_map = {}
            action = None
            
            try:
                # 3.1 Try OmniParser -> SoM
                elements = await self.omni_client.parse_screenshot(screenshot_before_b64)
                loop = asyncio.get_running_loop()
                annotated_b64, id_map = await loop.run_in_executor(
                    None, self.som_renderer.draw_som, screenshot_before_b64, elements
                )
                som_text_lines = []
                for k, v in id_map.items():
                    bbox = v.get('bbox', [0, 0, 0, 0])
                    w = int(bbox[2] - bbox[0])
                    h = int(bbox[3] - bbox[1])
                    som_text_lines.append(f"ID {k}: [{w}x{h}] {v.get('label')} {v.get('content', '')}")
                som_text = "\n".join(som_text_lines)
                
                # 4.1 Visual Planning
                logger.info(f"🧠 [execute_step] 视觉规划: {description}")
                action = await self.planner.plan_next_step(
                    description, annotated_b64, som_text, []
                )
                
                # 4.2 Task-aware action correction
                if action:
                    action = self._correct_action_type(action, description)

            except Exception as e:
                logger.warning(f"⚠️ 视觉感知/规划失败: {e}，切换到 DOM Fallback 模式")
                
                # 3.2 DOM Perception
                id_map = {} # Clear ID map as we are in DOM mode
                dom = await self.dom_service.get_simplified_dom(self.page)
                
                # 4.2 DOM Planning
                logger.info(f"🧠 [execute_step] DOM 兜底规划: {description}")
                action = await self.planner.plan_fallback_step(
                    description, dom, screenshot_before_b64
                )
                # Fallback mode uses original screenshot
                annotated_b64 = screenshot_before_b64
            
            if not action or action.action_type == "done":
                result["success"] = True
                result["action_taken"] = "done"
                result["target_description"] = "目标已达成"
                result["screenshot_after"] = screenshot_before_b64
                return result
            
            # Step 5: 执行
            logger.info(f"🖱️ [execute_step] 执行: {action.action_type} → {action.target}")
            success = await self.runner.execute(action, id_map)
            
            # Step 6: 执行后截图
            if self.waiter:
                await self.waiter.wait_until_stable()
            screenshot_after_bytes = await self.page.screenshot(type="png")
            screenshot_after_b64 = base64.b64encode(screenshot_after_bytes).decode("utf-8")
            
            result["success"] = success
            result["action_taken"] = action.action_type
            result["target_description"] = str(action.target) if action.target else description
            result["screenshot_after"] = screenshot_after_b64
            result["page_url"] = self.page.url
            result["page_title"] = await self.page.title()
            
            if not success:
                result["error"] = f"动作 {action.action_type} 执行失败"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [execute_step] 错误: {e}")
            # 尝试捕获错误截图
            try:
                err_bytes = await self.page.screenshot(type="png")
                result["screenshot_after"] = base64.b64encode(err_bytes).decode("utf-8")
                result["page_url"] = self.page.url
            except Exception:
                pass
            result["error"] = str(e)
            return result


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
