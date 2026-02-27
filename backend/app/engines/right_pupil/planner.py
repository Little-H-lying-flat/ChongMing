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

# ═══════════════════════════════════════════════════════
# 视觉规划提示词 (Visual Planning Prompt)
# ═══════════════════════════════════════════════════════
VISUAL_PLAN_PROMPT = """\
你是一个精准的 UI 自动化代理（Visual UI Automation Agent）。
你收到一张经过 Set-of-Mark (SoM) 标注的屏幕截图和一个任务目标，需要规划下一步操作。

━━━━━━━━━━ 任务 ━━━━━━━━━━
{task_description}

━━━━━━━━━━ 历史操作 ━━━━━━━━━━
{history}

━━━━━━━━━━ 当前屏幕 ━━━━━━━━━━
截图中每个可交互元素已用红色矩形框标记，左上角标注了元素 ID。
元素列表（格式: ID N: [宽x高] 类型 内容）:
{som_text}

━━━━━━━━━━ 核心规则 ━━━━━━━━━━

■ 元素选择规则（按操作类型）:
  • type（输入文本）→ 必须选择 input/textarea/搜索框等【可编辑区域】
    ✗ 禁止选择: 图标(icon)、按钮(button)、标签(label)、放大镜、发送按钮
    ✓ 正确选择: 文本输入框（通常是长条形、有边框或背景色的可编辑区域）
  • click（点击）→ 选择按钮、链接、菜单项、Tab、复选框等可点击元素
  • scroll（滚动）→ 不需要 target，仅设置 params 中的 x/y 偏移量
  • wait（等待）→ 不需要 target，仅设置 params.seconds
  • navigate（跳转）→ 不需要 target，仅设置 params.url

■ 元素歧义消解:
  当多个元素看起来相关时（如搜索图标 vs 搜索输入框）:
  1. 阅读任务描述中的动词: "输入"→选输入框，"点击"→选按钮
  2. 利用尺寸 [宽x高] 判断: 宽度远大于高度(如 [400x30])→输入框，
     近似正方形(如 [30x30])→图标/按钮
  3. 如果标签含有 "icon/图标/button/按钮"，且当前操作是 type，则跳过该元素

■ 任务完成判断:
  如果截图显示任务已经完成（目标状态已达成），返回 action_type 为 "done"。

━━━━━━━━━━ 输出格式（严格 JSON） ━━━━━━━━━━
仅返回一个 JSON 对象，不要包含多余文字或代码块标记:
{{
    "action_type": "click | type | scroll | wait | navigate | done",
    "target": {{
        "strategy": "visual",
        "value": "<元素 ID 数字>",
        "description": "<元素的简短描述>"
    }},
    "params": {{
        "text": "<输入内容，仅 type 操作需要>",
        "url": "<跳转地址，仅 navigate 操作需要>",
        "seconds": <等待秒数，仅 wait 操作需要>,
        "x": <水平滚动量，仅 scroll 操作需要>,
        "y": <垂直滚动量，仅 scroll 操作需要>
    }},
    "expected_visual_change": "<操作后页面应出现的变化>"
}}

注意:
- target.value 必须是元素列表中存在的 ID 数字（字符串格式）
- params 中只包含当前操作所需的字段，其余省略
- scroll/wait/navigate/done 操作的 target 可以为 null
"""

# ═══════════════════════════════════════════════════════
# DOM 兜底规划提示词 (DOM Fallback Prompt)
# ═══════════════════════════════════════════════════════
DOM_FALLBACK_PROMPT = """\
视觉识别已失败，现在使用 DOM 结构作为备选方案来完成任务。

━━━━━━━━━━ 任务 ━━━━━━━━━━
{task_description}

━━━━━━━━━━ DOM 结构 ━━━━━━━━━━
{dom_tree}

━━━━━━━━━━ 选择规则 ━━━━━━━━━━
1. 分析 DOM 树，找到能完成当前步骤的最佳元素
2. 策略 (strategy) 必须设为 "dom"
3. value 使用稳定的 CSS 选择器:
   优先级: [data-testid] > [id] > [name] > [aria-label] > 组合选择器
   ✗ 避免: nth-child、过长的层级路径
4. 输入类操作（type）必须选择 input/textarea 元素

━━━━━━━━━━ 输出格式（严格 JSON） ━━━━━━━━━━
仅返回一个 JSON 对象:
{{
    "action_type": "click | type | scroll | wait",
    "target": {{
        "strategy": "dom",
        "value": "<CSS 选择器>",
        "description": "<元素描述>"
    }},
    "params": {{}},
    "expected_visual_change": "<预期变化>"
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
                module=AIModule.AGENT_RIGHT_VISUAL,
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
                 module=AIModule.AGENT_RIGHT_VISUAL,
                 prompt=prompt,
                 image_base64=screenshot_base64
            )
            
            return self._parse_llm_response(response.content)
            
        except Exception as e:
            logger.error(f"Fallback Planning Failed: {e}")
            return None

    def _parse_llm_response(self, response: str) -> Optional[VisualActionIR]:
        """解析 LLM 返回的 JSON，容错处理各种输出格式"""
        import re
        try:
            text = response.strip()
            
            # 1. 提取代码块中的 JSON（```json ... ``` 或 ``` ... ```）
            code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
            if code_block:
                text = code_block.group(1).strip()
            
            # 2. 提取第一个 {...} JSON 对象（忽略前后多余文本）
            brace_match = re.search(r'\{.*\}', text, re.DOTALL)
            if brace_match:
                text = brace_match.group(0)
            
            # 3. 移除可能的尾部逗号 (trailing comma)
            text = re.sub(r',\s*([}\]])', r'\1', text)
            
            data = json.loads(text)
            return VisualActionIR(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse Action IR: {e}, Response: {response[:500]}")
            return None

