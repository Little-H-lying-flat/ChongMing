
import asyncio
import logging
import time
import io
import numpy as np
from PIL import Image
from playwright.async_api import Page
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

class SmartWaiter:
    """
    智能等待器 (Smart Waiter)
    
    采用 Visual (SSIM) + Network (Idle) 双重信号检测页面稳定性。
    不依赖 DOM 变动检测，更符合 Visual-First 策略。
    """
    
    def __init__(self, page: Page):
        self.page = page

    async def wait_until_stable(
        self, 
        timeout: float = 10.0, 
        visual_threshold: float = 0.99,
        poll_interval: float = 0.5
    ) -> bool:
        """
        等待页面稳定
        
        流程:
        1. Network Idle: 等待网络请求平息 (默认 500ms 无请求)
        2. Visual Stability: 连续两帧截图 SSIM > threshold
        
        Args:
            timeout: 总超时时间 (秒)
            visual_threshold: 视觉相似度阈值 (0.0 - 1.0, 推荐 0.99)
            poll_interval: 视觉检测轮询间隔 (秒)
            
        Returns:
            bool: True if stable, False if timeout
        """
        start_time = time.time()
        
        try:
            # 1. Network Stability (快速失败/通过)
            # 使用 Playwright 内置 networkidle，超时设为剩余时间的一部分
            # networkidle 意味着至少 500ms 没有网络连接
            network_timeout = max(2000, (timeout * 1000) / 2) # 分配一半时间给网络
            try:
                await self.page.wait_for_load_state("networkidle", timeout=network_timeout)
                logger.debug("Network is idle.")
            except Exception:
                logger.warning("Network idle timeout, proceeding to visual check anyway.")

            # 2. Visual Stability Loop
            last_image = await self._capture_screenshot()
            
            while (time.time() - start_time) < timeout:
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    break
                
                await asyncio.sleep(poll_interval)
                
                current_image = await self._capture_screenshot()
                
                similarity = self._calculate_ssim(last_image, current_image)
                logger.debug(f"Visual SSIM: {similarity:.4f}")
                
                if similarity >= visual_threshold:
                    logger.info(f"Page is visually stable (SSIM: {similarity:.4f})")
                    return True
                
                last_image = current_image
                
            logger.warning("SmartWait timeout reached via Visual Check.")
            return False
            
        except Exception as e:
            logger.error(f"SmartWait failed: {e}")
            return False

    async def _capture_screenshot(self) -> np.ndarray:
        """捕获截图并转换为灰度 numpy 数组"""
        screenshot_bytes = await self.page.screenshot(type="png")
        image = Image.open(io.BytesIO(screenshot_bytes)).convert("L") # 转为灰度
        return np.array(image)

    def _calculate_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """计算两张图片的 SSIM"""
        if img1.shape != img2.shape:
             # 如果尺寸变化，说明发生剧烈变动 (Resize?)，视为不稳定 0.0
             # 但通常 screenshot 尺寸一致。例外: viewport change
             return 0.0
             
        # win_size 必须小于图像尺寸的最小边
        min_side = min(img1.shape)
        win_size = min(7, min_side if min_side % 2 == 1 else min_side - 1)
        if win_size < 3: win_size = None # 使用默认
            
        score, _ = ssim(img1, img2, full=True, win_size=win_size)
        return score
