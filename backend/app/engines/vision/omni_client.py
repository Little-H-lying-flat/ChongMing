"""
OmniParser Client
右瞳引擎视觉感知客户端

负责与 OmniParser 服务进行交互，提取 UI 元素坐标和描述。
"""

import base64
import logging
from typing import List, Dict, Any, Tuple, Optional
import httpx
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)

class OmniElement(BaseModel):
    """OmniParser 识别出的元素"""
    id: int
    label: str
    box_2d: List[int] # [x_min, y_min, x_max, y_max]
    content: Optional[str] = None

class OmniClient:
    """
    OmniParser 服务客户端
    """
    
    def __init__(self, base_url: str = "", client: Optional[httpx.AsyncClient] = None):
        self.base_url = (base_url or settings.OMNIPARSER_URL).rstrip("/")
        self.timeout = 300.0 # Increased for CPU inference / initial download
        self._client = client
        self._internal_client: Optional[httpx.AsyncClient] = None
        
    async def get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端 (共享或内部)"""
        if self._client:
            return self._client
        
        if not self._internal_client or self._internal_client.is_closed:
            self._internal_client = httpx.AsyncClient(timeout=self.timeout)
            
        return self._internal_client

    async def parse_screenshot(self, image_base64: str) -> List[OmniElement]:
        """
        解析屏幕截图
        
        Args:
            image_base64: Base64 编码的图片字符串 (支持带 header)
            
        Returns:
            List[OmniElement]: 识别出的元素列表
        """
        # 1. Mock Mode Check
        if settings.MOCK_OMNIPARSER:
            logger.warning("OmniParser Mock Mode Enabled - Returning fake data")
            return [
                OmniElement(id=0, label="search_box", box_2d=[100, 100, 500, 150], content="Search"),
                OmniElement(id=1, label="search_button", box_2d=[510, 100, 600, 150], content="Google Search"),
                OmniElement(id=2, label="text", box_2d=[50, 50, 200, 80], content="Gmail"),
            ]

        # 2. 清理 Base64 头部
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
            
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                client = await self.get_client()
                response = await client.post(
                    f"{self.base_url}/parse",
                    json={"base64_image": image_base64},
                )
                response.raise_for_status()
                data = response.json()
                
                # 假设 OmniParser 返回格式:
                # {"layout": [{"id": 0, "box_2d": [x1, y1, x2, y2], "label": "button"}, ...]}
                elements_data = data.get("layout", [])
                
                elements = []
                for idx, item in enumerate(elements_data):
                    # 处理可能的不同返回结构，确保兼容
                    box = item.get("box_2d") or item.get("bbox")
                    label = item.get("label") or item.get("text") or "element"
                    content = item.get("content")
                    
                    if box:
                        elements.append(OmniElement(
                            id=idx,
                            label=label,
                            box_2d=box,
                            content=content
                        ))
                        
                logger.info(f"OmniParser 成功识别 {len(elements)} 个元素")
                if len(elements) > 0:
                    logger.info(f"First 3 elements: {elements[:3]}") # Force INFO logging
                return elements
                    
            except httpx.HTTPStatusError as e:
                # 5xx 服务端错误 → 重试
                if e.response.status_code >= 500 and attempt < max_retries:
                    wait = 2 ** (attempt + 1)  # 2s, 4s
                    logger.warning(f"OmniParser 返回 {e.response.status_code}, 第 {attempt+1}/{max_retries} 次重试, 等待 {wait}s...")
                    import asyncio
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"OmniParser HTTP 错误 {e.response.status_code}: {e}")
                raise RuntimeError(f"OmniParser 解析失败: {str(e)}") from e
            except httpx.RequestError as e:
                logger.error(f"OmniParser 连接失败: {e}")
                raise RuntimeError(f"OmniParser 服务无法连接: {self.base_url}") from e
            except Exception as e:
                logger.error(f"OmniParser 解析错误: {e}")
                raise RuntimeError(f"OmniParser 解析失败: {str(e)}") from e

    async def close(self):
        """关闭内部客户端"""
        if self._internal_client:
            await self._internal_client.aclose()
            self._internal_client = None
