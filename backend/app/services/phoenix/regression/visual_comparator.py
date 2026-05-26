
import io
from typing import Optional, Tuple

import numpy as np
from PIL import Image
from loguru import logger
from skimage.metrics import structural_similarity as ssim


class VisualComparator:
    """视觉比较器：使用 SSIM 计算结构相似度并生成 Diff 图片。"""

    async def compare(self,
                      baseline_bytes: bytes,
                      current_bytes: bytes,
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

            # 2. Convert to Grayscale for SSIM
            gray_base = np.array(img_base.convert("L"))
            gray_curr = np.array(img_curr.convert("L"))
            
            # 3. Calculate SSIM
            score, diff = ssim(gray_base, gray_curr, full=True)
            logger.info(f"Visual SSIM Score: {score:.4f}")
            
            if score >= threshold:
                return True, score, None
            
            # 4. Generate Diff Image
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
