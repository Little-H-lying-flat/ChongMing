"""
AUI-IR (Abstract User Interface Intermediate Representation)
右瞳引擎视觉协议定义

用于描述基于视觉的 UI 自动化动作和定位策略。
"""

from typing import List, Optional, Literal, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
import uuid

# 定位策略类型
TargetStrategy = Literal["visual", "dom", "ocr", "point"]

class VisualLocator(BaseModel):
    """
    视觉定位器
    
    描述如何在屏幕上定位一个元素
    """
    strategy: TargetStrategy = Field(
        ..., 
        description="定位策略: visual(图像识别), dom(DOM树), ocr(文字识别), point(坐标)"
    )
    value: Optional[str] = Field(
        None, 
        description="定位值 (Selector, OCR文本, Description)"
    )
    description: Optional[str] = Field(
        None, 
        description="元素的自然语言描述，用于辅助定位或 Debug"
    )
    bbox: Optional[List[Union[int, float]]] = Field(
        None, 
        description="边界框 [x_min, y_min, x_max, y_max]，Visual/OCR 识别结果"
    )
    confidence: Optional[float] = Field(
        None, 
        ge=0, le=1, 
        description="识别置信度 (0.0 - 1.0)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy": "visual",
                "value": "login_button",
                "description": "Red generic login button on top right",
                "bbox": [100, 200, 150, 250],
                "confidence": 0.98
            }
        }
    )

class VisualActionIR(BaseModel):
    """
    动作中间表示 (AUI-IR)
    
    描述一个具体的 UI 操作步骤
    """
    id: str = Field(
        default_factory=lambda: f"ACT_{uuid.uuid4().hex[:8]}",
        description="动作唯一标识"
    )
    action_type: Literal[
        "click", "dblclick", "hover", 
        "type", "press", 
        "scroll", "drag_and_drop",
        "wait", "screenshot", "navigate",
        "assert_visible", "assert_text"
    ] = Field(..., description="动作类型")
    
    target: Optional[VisualLocator] = Field(
        None, 
        description="操作目标元素 (Wait/Navigate 等全局操作可为空)"
    )
    
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="动作参数 (如 text, keys, scroll_delta_x/y, url, timeout)"
    )
    
    expected_visual_change: Optional[str] = Field(
        None, 
        description="预期的视觉变化描述 (用于验证动作成功)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "ACT_12345678",
                "action_type": "click",
                "target": {
                    "strategy": "visual",
                    "description": "Submit Button",
                    "bbox": [500, 500, 600, 550]
                },
                "params": {"verify_success": True},
                "expected_visual_change": "Page navigates to dashboard"
            }
        }
    )
