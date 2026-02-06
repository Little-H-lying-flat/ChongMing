"""
右瞳引擎 (Right Pupil Engine)

所属层级：执行层 (Execution Layer) - UI 侧
设计哲学：Visual-First, DOM-Fallback (视觉主导，结构兜底)

核心职责:
- 视觉感知 (Visual Perception)：截图 + OmniParser 识别页面元素
- 结构感知 (Structural Perception)：DOM 树剪枝，生成精简 HTML
- 融合决策 (Fusion Decision)：Qwen3-VL-Plus 多模态推理
- 原子执行 (Atomic Execution)：坐标点击 / 选择器点击
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from pathlib import Path
import asyncio

from loguru import logger
from playwright.async_api import Page, Locator

from app.core.config import settings


class ExecutionStrategy(Enum):
    """执行策略"""
    VISUAL = "visual"  # 视觉坐标
    DOM = "dom"        # DOM 选择器
    HYBRID = "hybrid"  # 混合模式


class ExecutionMode(Enum):
    """执行模式 (双模态执行)"""
    PLANNING = "planning"  # 规划模式 (默认)
    ATOMIC = "atomic"      # 原子模式 (跳过规划)


@dataclass
class ElementInfo:
    """元素信息"""
    label: str
    coordinates: tuple[int, int]
    selector: Optional[str] = None
    confidence: float = 0.0
    bounding_box: Optional[dict] = None


@dataclass
class ActionResult:
    """动作执行结果"""
    success: bool
    strategy_used: ExecutionStrategy
    element: Optional[ElementInfo] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class AUIIR:
    """AUI-IR 协议 (Atomic UI Intermediate Representation)"""
    action: str  # click, input, hover, scroll, verify
    target: str  # 自然语言描述
    value: Optional[str] = None
    selector: Optional[str] = None
    coordinates: Optional[tuple[int, int]] = None
    expected: Optional[str] = None


class RightPupilEngine:
    """
    右瞳引擎 - UI 自动化执行核心
    
    工作流程:
    1. 智能等待页面稳定
    2. 截图并调用 OmniParser 识别元素
    3. VLM 融合决策，选择目标元素
    4. 执行动作 (优先视觉坐标，失败则 DOM 兜底)
    5. 验证执行结果
    """
    
    def __init__(
        self,
        omniparser_url: str = None,
        execution_mode: ExecutionMode = ExecutionMode.PLANNING,
    ):
        self.omniparser_url = omniparser_url or settings.OMNIPARSER_URL
        self.execution_mode = execution_mode
        self._page: Optional[Page] = None
        
    async def attach(self, page: Page):
        """附加到 Playwright Page"""
        self._page = page
        logger.info("右瞳引擎已附加到页面")
    
    async def execute(self, action: AUIIR) -> ActionResult:
        """
        执行 AUI-IR 动作
        
        Args:
            action: AUI-IR 动作描述
            
        Returns:
            ActionResult: 执行结果
        """
        if not self._page:
            raise RuntimeError("引擎未附加到页面，请先调用 attach()")
        
        logger.info(f"执行动作: {action.action} -> {action.target}")
        
        try:
            # 1. 智能等待
            await self._smart_wait()
            
            # 2. 截图
            screenshot_before = await self._take_screenshot("before")
            
            # 3. 元素定位
            element = await self._locate_element(action)
            
            # 4. 执行动作
            result = await self._perform_action(action, element)
            
            # 5. 截图
            screenshot_after = await self._take_screenshot("after")
            
            result.screenshot_before = screenshot_before
            result.screenshot_after = screenshot_after
            
            return result
            
        except Exception as e:
            logger.error(f"执行失败: {e}")
            return ActionResult(
                success=False,
                strategy_used=ExecutionStrategy.VISUAL,
                error=str(e),
            )
    
    async def _smart_wait(self, timeout_ms: int = 5000):
        """
        智能等待 - 多信号融合
        
        等待信号:
        - 网络空闲 (无待完成请求)
        - DOM 稳定 (无变化)
        - 视觉稳定 (截图 Hash 一致)
        """
        # TODO: 实现多信号融合等待
        await self._page.wait_for_load_state("networkidle")
    
    async def _take_screenshot(self, suffix: str = "") -> str:
        """截图并保存"""
        screenshot_dir = Path(settings.SCREENSHOT_DIR)
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        import time
        filename = f"screenshot_{int(time.time()*1000)}_{suffix}.png"
        path = screenshot_dir / filename
        
        await self._page.screenshot(path=str(path))
        return str(path)
    
    async def _locate_element(self, action: AUIIR) -> ElementInfo:
        """
        元素定位 - Visual-First 策略
        
        1. 如果有坐标，直接使用
        2. 否则调用 OmniParser 识别
        3. VLM 融合决策选择目标
        """
        if action.coordinates:
            return ElementInfo(
                label=action.target,
                coordinates=action.coordinates,
                confidence=1.0,
            )
        
        if action.selector:
            # DOM 定位兜底
            try:
                locator = self._page.locator(action.selector)
                box = await locator.bounding_box()
                if box:
                    center = (int(box["x"] + box["width"] / 2), 
                              int(box["y"] + box["height"] / 2))
                    return ElementInfo(
                        label=action.target,
                        coordinates=center,
                        selector=action.selector,
                        confidence=0.9,
                        bounding_box=box,
                    )
            except Exception as e:
                logger.warning(f"DOM 定位失败: {e}")
        
        # TODO: 调用 OmniParser + VLM 视觉定位
        raise NotImplementedError("OmniParser 视觉定位尚未实现")
    
    async def _perform_action(
        self, 
        action: AUIIR, 
        element: ElementInfo
    ) -> ActionResult:
        """
        执行动作 - 双路径策略
        
        主路径: 视觉坐标
        兜底: DOM 选择器
        """
        start_time = asyncio.get_event_loop().time()
        strategy = ExecutionStrategy.VISUAL
        
        try:
            if action.action == "click":
                await self._page.mouse.click(
                    element.coordinates[0], 
                    element.coordinates[1]
                )
                
            elif action.action == "input":
                await self._page.mouse.click(
                    element.coordinates[0], 
                    element.coordinates[1]
                )
                await self._page.keyboard.type(action.value or "")
                
            elif action.action == "hover":
                await self._page.mouse.move(
                    element.coordinates[0], 
                    element.coordinates[1]
                )
                
            elif action.action == "scroll":
                delta = int(action.value or 300)
                await self._page.mouse.wheel(0, delta)
                
            else:
                raise ValueError(f"不支持的动作类型: {action.action}")
            
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return ActionResult(
                success=True,
                strategy_used=strategy,
                element=element,
                duration_ms=duration,
            )
            
        except Exception as e:
            # 尝试 DOM 兜底
            if element.selector:
                try:
                    strategy = ExecutionStrategy.DOM
                    locator = self._page.locator(element.selector)
                    
                    if action.action == "click":
                        await locator.click()
                    elif action.action == "input":
                        await locator.fill(action.value or "")
                    elif action.action == "hover":
                        await locator.hover()
                    
                    duration = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    return ActionResult(
                        success=True,
                        strategy_used=strategy,
                        element=element,
                        duration_ms=duration,
                    )
                except Exception as e2:
                    return ActionResult(
                        success=False,
                        strategy_used=strategy,
                        element=element,
                        error=f"Visual failed: {e}, DOM failed: {e2}",
                    )
            
            return ActionResult(
                success=False,
                strategy_used=strategy,
                element=element,
                error=str(e),
            )
