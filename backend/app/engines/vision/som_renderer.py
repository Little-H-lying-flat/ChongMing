"""
Set-of-Mark (SoM) Renderer
右瞳引擎视觉标注服务

负责在截图上绘制边界框和数字标签，辅助 VLM 进行定位。
"""

import base64
import io
from typing import List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont

from app.engines.vision.omni_client import OmniElement

class SoMRenderer:
    """
    Set-of-Mark 渲染器
    """
    
    @staticmethod
    def draw_som(image_base64: str, elements: List[OmniElement]) -> Tuple[str, Dict[int, Dict[str, Any]]]:
        """
        在图片上绘制 SoM 标记
        
        Args:
            image_base64: 原始图片 Base64
            elements: OmniParser 识别出的元素列表
            
        Returns:
            Tuple[str, Dict]:
            - 标注后的图片 Base64
            - ID 映射表 {id: {"center": (x, y), "label": label}}
        """
        # 1. 解码图片
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
            
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        draw = ImageDraw.Draw(image)
        
        width, height = image.size
        id_map = {}
        
        # 尝试加载字体，如果失败使用默认
        try:
            # 尝试加载更清晰的字体，如 Arial 或系统中存在的字体
            # 这里简单处理，使用默认
            font = ImageFont.load_default()
            # font = ImageFont.truetype("arial.ttf", 15) 
        except Exception:
            font = ImageFont.load_default()

        for el in elements:
            box = el.box_2d
            # 处理归一化坐标 (假设如果坐标都在 0-1 之间，则为归一化)
            if all(0 <= x <= 1 for x in box):
                x1, y1, x2, y2 = box[0]*width, box[1]*height, box[2]*width, box[3]*height
            else:
                x1, y1, x2, y2 = box
                
            # 确保坐标在图片范围内
            x1 = max(0, min(x1, width))
            y1 = max(0, min(y1, height))
            x2 = max(0, min(x2, width))
            y2 = max(0, min(y2, height))
            
            # 绘制红色矩形框
            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            
            # 绘制标签背景和文本 (ID)
            # 标签位置：左上角
            text = str(el.id)
            # text_bbox = draw.textbbox((x1, y1), text, font=font) # Pillow >= 10
            # 使用简单的估计
            text_w = len(text) * 10 
            text_h = 14
            
            # 绘制标签背景 (黑色背景，白色文字，高对比度)
            draw.rectangle([x1, y1, x1 + text_w, y1 + text_h], fill="red")
            draw.text((x1 + 2, y1), text, fill="white", font=font)
            
            # 记录中心点
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            id_map[el.id] = {
                "center": (center_x, center_y),
                "bbox": [x1, y1, x2, y2],
                "label": el.label,
                "content": el.content
            }
            
        # 3. 编码回 Base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        annotated_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return annotated_base64, id_map
