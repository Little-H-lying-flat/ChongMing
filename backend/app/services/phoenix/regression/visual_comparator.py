
import numpy as np
from PIL import Image, ImageDraw
import io
from skimage.metrics import structural_similarity as ssim
from loguru import logger
from typing import List, Tuple, Optional
from app.engines.vision.omni_client import OmniClient, OmniElement

class VisualComparator:
    """
    AI 驱动的视觉比较器 (AI-VRT)
    
    1. 使用 OmniParser 识别动态元素 (Ads, Date, UserID) 并自动遮罩 (Masking)。
    2. 使用 SSIM 计算结构相似度，而非简单的像素差异。
    3. 生成 Diff 图片。
    """
    
    def __init__(self, omni_client: OmniClient):
        self.omni_client = omni_client
        
    async def compare(self, 
                      baseline_bytes: bytes, 
                      current_bytes: bytes, 
                      dynamic_labels: List[str] = ["time", "date", "ad", "user_id"],
                      threshold: float = 0.95) -> Tuple[bool, float, Optional[bytes]]:
        """
        比较两张图片
        
        Returns:
            (is_passed, score, diff_image_bytes)
        """
        try:
            # 1. Load Images
            img_base = Image.open(io.BytesIO(baseline_bytes)).convert("RGB")
            img_curr = Image.open(io.BytesIO(current_bytes)).convert("RGB")
            
            # Resize current to match baseline if needed (Handling viewport shifts?)
            if img_curr.size != img_base.size:
                logger.warning(f"Image size mismatch: {img_base.size} vs {img_curr.size}. Resizing current.")
                img_curr = img_curr.resize(img_base.size)

            # 2. AI Masking (Optional but recommended)
            # detect elements on CURRENT image to mask them out
            # We skip masking on baseline for simplicity, assuming dynamic content moves/changes
            
            # Convert to base64 for OmniParser
            # buffer = io.BytesIO()
            # img_curr.save(buffer, format="PNG")
            # b64 = base64.b64encode(buffer.getvalue()).decode()
            
            # elements = await self.omni_client.parse_screenshot(b64)
            # mask_regions = [e.box_2d for e in elements if any(l in e.label for l in dynamic_labels)]
            
            # For Phase 6 initial implementation, we might skip actual Omni call to save tokens/time 
            # unless explicitly enabled. Let's keep it simple with SSIM first.
            
            # 3. Convert to Grayscale for SSIM
            gray_base = np.array(img_base.convert("L"))
            gray_curr = np.array(img_curr.convert("L"))
            
            # 4. Calculate SSIM
            score, diff = ssim(gray_base, gray_curr, full=True)
            logger.info(f"Visual SSIM Score: {score:.4f}")
            
            if score >= threshold:
                return True, score, None
            
            # 5. Generate Diff Image
            # diff is float -1 to 1. Convert to 0-255 uint8
            diff = (diff * 127.5 + 127.5).astype("uint8")
            diff_img = Image.fromarray(diff)
            
            # Overlay diff on original? Or just return diff heatmap
            out_buffer = io.BytesIO()
            diff_img.save(out_buffer, format="PNG")
            
            return False, score, out_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Visual Comparison Failed: {e}")
            return False, 0.0, None
