
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
from PIL import Image
import io
import asyncio
from app.engines.vision.smart_waiter import SmartWaiter

def create_dummy_image_bytes(color=100):
    """Create a dummy 100x100 grayscale image bytes"""
    img = Image.new('L', (100, 100), color=color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

@pytest.mark.asyncio
async def test_smart_wait_stable():
    """Test wait_until_stable when page is stable immediately"""
    mock_page = AsyncMock()
    # Return same image twice
    img_bytes = create_dummy_image_bytes(100)
    mock_page.screenshot.return_value = img_bytes
    
    waiter = SmartWaiter(mock_page)
    
    # Run
    result = await waiter.wait_until_stable(timeout=2.0, poll_interval=0.1)
    
    assert result is True
    # Should call screenshot at least twice (initial + 1 check)
    assert mock_page.screenshot.call_count >= 2

@pytest.mark.asyncio
async def test_smart_wait_becomes_stable():
    """Test wait_until_stable when page becomes stable after change"""
    mock_page = AsyncMock()
    
    img1 = create_dummy_image_bytes(100)
    img2 = create_dummy_image_bytes(200) # Different
    
    # Sequence: img1, img2 (diff), img2 (stable)
    mock_page.screenshot.side_effect = [img1, img2, img2]
    
    waiter = SmartWaiter(mock_page)
    
    result = await waiter.wait_until_stable(timeout=2.0, poll_interval=0.1)
    
    assert result is True
    assert mock_page.screenshot.call_count >= 3

@pytest.mark.asyncio
async def test_smart_wait_timeout():
    """Test wait_until_stable timeout if page never stabilizes"""
    mock_page = AsyncMock()
    
    # Always return different images
    # We can use a side effect that increments color
    counter = 0
    def side_effect(*args, **kwargs):
        nonlocal counter
        counter += 1
        # Use large step to ensure different images
        val = (counter * 50) % 255
        return create_dummy_image_bytes(val)
        
    mock_page.screenshot.side_effect = side_effect
    
    waiter = SmartWaiter(mock_page)
    
    # Short timeout
    result = await waiter.wait_until_stable(timeout=1.0, poll_interval=0.1)
    
    assert result is False
