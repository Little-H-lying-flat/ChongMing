
import os
import json
import aiofiles
from typing import Dict, Any, Optional
from loguru import logger
from app.core.config import settings

class BaselineManager:
    """
    基准管理器 (Baseline Manager)
    
    负责存储和检索回归测试的"金样" (Golden Tape)。
    支持 Visual (Screenshots) 和 API (JSON Responses) 基准。
    """
    
    def __init__(self, base_dir: str = "baselines"):
        self.base_dir = base_dir
        # Ensure base directory exists
        os.makedirs(self.base_dir, exist_ok=True)
        
    def _get_path(self, test_id: str, variant: str, ext: str) -> str:
        return os.path.join(self.base_dir, f"{test_id}_{variant}.{ext}")

    async def save_baseline_image(self, test_id: str, image_bytes: bytes):
        """保存视觉基准"""
        path = self._get_path(test_id, "visual", "png")
        async with aiofiles.open(path, "wb") as f:
            await f.write(image_bytes)
        logger.info(f"Saved visual baseline for {test_id} at {path}")

    async def get_baseline_image(self, test_id: str) -> Optional[bytes]:
        """获取视觉基准"""
        path = self._get_path(test_id, "visual", "png")
        if not os.path.exists(path):
            return None
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def save_baseline_api(self, test_id: str, data: Dict[str, Any]):
        """保存 API 基准"""
        path = self._get_path(test_id, "api", "json")
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info(f"Saved API baseline for {test_id} at {path}")

    async def get_baseline_api(self, test_id: str) -> Optional[Dict[str, Any]]:
        """获取 API 基准"""
        path = self._get_path(test_id, "api", "json")
        if not os.path.exists(path):
            return None
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
            
    def baseline_exists(self, test_id: str, kind: str = "api") -> bool:
        ext = "json" if kind == "api" else "png"
        path = self._get_path(test_id, kind, ext)
        return os.path.exists(path)
