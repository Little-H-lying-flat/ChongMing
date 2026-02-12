"""
Visual Planner (The Brain)
右瞳引擎视觉规划器

负责基于视觉感知 (SoM) 和 DOM 信息，利用 LLM 决策下一步操作。
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from app.core.ai_client import get_ai_manager, AIModule
from app.schemas.aui_ir import VisualActionIR

logger = logging.getLogger(__name__)

# 视觉规划提示词
VISUAL_PLAN_PROMPT = """
你是一个 UI 自动化代理。你的目标是根据当前屏幕截图和任务描述，规划下一步操作。

### 任务
{task_description}

### 上下文
{history}

### 屏幕信息
截图已使用 Set-of-Mark (SoM) 标记。
元素列表 (ID -> 描述):
{som_text}

### 指令
1. 观察截图中的标记元素。
2. 结合任务目标，选择正确的元素进行操作。
3. 如果操作是点击/输入，优先使用 screenshot 中的 ID。
4. 返回符合 VisualActionIR 格式的 JSON。

### 输出格式 (JSON)
{{
    "action_type": "click" | "type" | "scroll" | "wait" | "navigate",
    "target": {{
        "strategy": "visual",
        "value": "元素ID",
        "description": "元素描述"
    }},
    "params": {{ "text": "输入内容" (如果需要) }},
    "expected_visual_change": "操作后的预期变化"
}}
"""

# DOM 兜底规划提示词
DOM_FALLBACK_PROMPT = """
视觉识别失败，正在尝试使用 DOM 结构进行恢复。

### 任务
{task_description}

### DOM 结构 (简化版)
{dom_tree}

### 指令
1. 分析 DOM 树，找到能完成当前步骤的最佳元素。
2. 生成一个基于 CSS Selector 的操作指令。
3. 策略 (strategy) 必须设为 "dom"。

### 输出格式 (JSON)
{{
    "action_type": "click" | "type" | "scroll" | "wait",
    "target": {{
        "strategy": "dom",
        "value": "CSS选择器",
        "description": "元素描述"
    }},
    "params": {{ ... }},
    "expected_visual_change": "..."
}}
"""

class VisualPlanner:
    """
    视觉规划器
    """
    
    def __init__(self):
        self.ai_manager = get_ai_manager()
        
    async def plan_next_step(
        self, 
        task: str, 
        screenshot_base64: str, 
        som_text: str, 
        history: List[Dict]
    ) -> Optional[VisualActionIR]:
        """
        基于视觉信息规划下一步
        """
        try:
            # 构造 Prompt
            prompt = VISUAL_PLAN_PROMPT.format(
                task_description=task,
                history=json.dumps(history, indent=2, ensure_ascii=False),
                som_text=som_text
            )
            
            # invoke vison model
            response = await self.ai_manager.invoke_vision(
                module=AIModule.RIGHT_PUPIL_GROUNDING,
                prompt=prompt,
                image_base64=screenshot_base64
            )
            
            return self._parse_llm_response(response.content)
            
        except Exception as e:
            logger.error(f"Visual Planning Failed: {e}")
            return None

    async def plan_fallback_step(
        self, 
        task: str, 
        dom_tree: Dict, 
        screenshot_base64: str
    ) -> Optional[VisualActionIR]:
        """
        DOM 兜底规划
        """
        try:
            dom_str = json.dumps(dom_tree, ensure_ascii=False)[:10000] # 截断防止过长
            prompt = DOM_FALLBACK_PROMPT.format(
                task_description=task,
                dom_tree=dom_str
            )
            
            # DOM 模式下，图片作为辅助，也传入
            response = await self.ai_manager.invoke_vision(
                 module=AIModule.RIGHT_PUPIL_GROUNDING,
                 prompt=prompt,
                 image_base64=screenshot_base64
            )
            
            return self._parse_llm_response(response.content)
            
        except Exception as e:
            logger.error(f"Fallback Planning Failed: {e}")
            return None

    def _parse_llm_response(self, response: str) -> Optional[VisualActionIR]:
        """解析 LLM 返回的 JSON"""
        try:
            # 清理代码块标记
            cleaned = response.strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned)
            return VisualActionIR(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse Action IR: {e}, Response: {response}")
            return None
