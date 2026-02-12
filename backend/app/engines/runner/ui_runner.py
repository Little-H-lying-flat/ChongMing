"""
UI Runner (The Hands)
右瞳引擎执行器

负责执行基于视觉或 DOM 的操作指令。
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from playwright.async_api import Page

from app.schemas.aui_ir import VisualActionIR, VisualLocator
from app.engines.vision.dom_service import DomService

logger = logging.getLogger(__name__)

class UiRunner:
    """
    UI 动作执行器
    """
    
    def __init__(self, page: Page, dom_service: DomService):
        self.page = page
        self.dom_service = dom_service
        self.trace_logs: List[Dict[str, Any]] = []
        
    async def execute(self, action: VisualActionIR, id_map: Dict[int, Dict[str, Any]] = None) -> bool:
        """
        执行单个动作
        
        Args:
            action: AUI-IR 动作对象
            id_map: 视觉元素 ID 映射表 (from SoMRenderer), 用于 visual 策略
            
        Returns:
            bool: 执行是否成功
        """
        try:
            logger.info(f"Executing Action: {action.action_type} - {action.id}")
            
            # 记录开始时间
            start_time = datetime.now()
            trace_entry = {
                "step_id": action.id,
                "action_type": action.action_type,
                "timestamp": start_time.isoformat(),
                "status": "pending"
            }
            
            # 1. 导航 (Navigate)
            if action.action_type == "navigate":
                url = action.params.get("url")
                if url:
                    await self.page.goto(url)
                    trace_entry["details"] = f"Navigated to {url}"
                else:
                    raise ValueError("Navigate action missing 'url' param")

            # 2. 等待 (Wait)
            elif action.action_type == "wait":
                seconds = action.params.get("seconds", 1)
                await asyncio.sleep(seconds)
                trace_entry["details"] = f"Waited {seconds}s"

            # 3. 点击 (Click) / 双击 (DblClick) / 输入 (Type)
            elif action.action_type in ["click", "dblclick", "type", "hover"]:
                if not action.target:
                    raise ValueError(f"Action {action.action_type} requires a target")
                
                await self._handle_interaction(action, id_map, trace_entry)

            # 4. 截图 (Screenshot)
            elif action.action_type == "screenshot":
                path = action.params.get("path", "screenshot.png")
                await self.page.screenshot(path=path)
                trace_entry["details"] = f"Screenshot saved to {path}"
                
            # 5. 滚动 (Scroll)
            elif action.action_type == "scroll":
                x = action.params.get("x", 0)
                y = action.params.get("y", 0)
                await self.page.mouse.wheel(x, y)
                trace_entry["details"] = f"Scrolled {x}, {y}"

            trace_entry["status"] = "success"
            self.trace_logs.append(trace_entry)
            return True

        except Exception as e:
            logger.error(f"Action Execution Failed: {e}")
            trace_entry["status"] = "failed"
            trace_entry["error"] = str(e)
            self.trace_logs.append(trace_entry)
            return False

    async def _handle_interaction(self, action: VisualActionIR, id_map: Dict[int, Dict[str, Any]], trace_entry: Dict):
        """处理交互逻辑 (Click, Type, etc.)"""
        target = action.target
        strategy = target.strategy
        
        x, y = 0, 0
        selector = None
        
        # A. Visual Strategy (通过 ID Map 获取坐标)
        if strategy == "visual":
            # value 应为 SoM ID (string or int)
            try:
                visual_id = int(target.value)
            except (ValueError, TypeError):
                 raise ValueError(f"Visual strategy requires integer ID, got {target.value}")

            if not id_map or visual_id not in id_map:
                raise ValueError(f"Visual ID {visual_id} not found in current frame")
            
            element_info = id_map[visual_id]
            x, y = element_info["center"]
            trace_entry["coords"] = {"x": x, "y": y}
            
            # 关键：嗅探 Selector 以增强稳定性
            selector = await self.dom_service.sniff_selector(self.page, x, y)
            if selector:
                trace_entry["stable_selector"] = selector
                logger.info(f"Sniffed selector for visual element {visual_id}: {selector}")
            
            # 执行动作 (优先使用 Playwright 的 locator 如果嗅探成功，否则用坐标)
            # 策略：为了模拟最真实的视觉操作，且 OmniParser 坐标通常即见即所得，
            # 我们优先使用坐标点击。如果失败再考虑 selector。
            # 但用户提示词要求： "在点击前调用 sniff_selector... 然后执行 page.mouse.click"
            # 这意味着 sniff 主要是为了记录(trace)和可能的后续恢复，但动作本身是用鼠标坐标。
            
            if action.action_type == "click":
                await self.page.mouse.click(x, y)
            elif action.action_type == "dblclick":
                await self.page.mouse.dblclick(x, y)
            elif action.action_type == "hover":
                await self.page.mouse.move(x, y)
            elif action.action_type == "type":
                await self.page.mouse.click(x, y) # 先聚焦
                text = action.params.get("text", "")
                await self.page.keyboard.type(text)

        # B. DOM Strategy (传统 Selector)
        elif strategy == "dom":
            selector = target.value
            if not selector:
                raise ValueError("DOM strategy requires a selector value")
            
            trace_entry["stable_selector"] = selector
            locator = self.page.locator(selector).first
            
            if action.action_type == "click":
                await locator.click()
            elif action.action_type == "dblclick":
                await locator.dblclick()
            elif action.action_type == "hover":
                await locator.hover()
            elif action.action_type == "type":
                text = action.params.get("text", "")
                await locator.fill(text)

        # C. Point Strategy (直接坐标)
        elif strategy == "point":
            # value 可能是 "x,y"
            if target.bbox:
                # 使用 bbox 中心
                x = (target.bbox[0] + target.bbox[2]) / 2
                y = (target.bbox[1] + target.bbox[3]) / 2
            elif "," in str(target.value):
                parts = str(target.value).split(",")
                x, y = float(parts[0]), float(parts[1])
            else:
                raise ValueError("Point strategy requires bbox or 'x,y' value")

            trace_entry["coords"] = {"x": x, "y": y}
            if action.action_type == "click":
                await self.page.mouse.click(x, y)
            elif action.action_type == "type":
                await self.page.mouse.click(x, y)
                await self.page.keyboard.type(action.params.get("text", ""))

        else:
            raise NotImplementedError(f"Strategy {strategy} not supported yet")
