import pytest
from app.engines.vision.omni_client import OmniClient, OmniElement
from app.core.config import settings

@pytest.mark.asyncio
async def test_omni_client_mock_mode():
    """Verify OmniClient returns mock data when MOCK_OMNIPARSER is True"""
    # Force Mock Mode
    original_mock = settings.MOCK_OMNIPARSER
    settings.MOCK_OMNIPARSER = True
    
    try:
        client = OmniClient()
        # Mock base64 image (doesn't matter for mock mode)
        elements = await client.parse_screenshot("base64_image_placeholder")
        
        assert len(elements) > 0
        assert isinstance(elements[0], OmniElement)
        assert elements[0].label in ["search_box", "search_button", "text"]
        
    finally:
        # Restore original setting
        settings.MOCK_OMNIPARSER = original_mock
        await client.close()

@pytest.mark.asyncio
async def test_omni_client_initialization():
    """Verify OmniClient initializes with correct defaults"""
    client = OmniClient()
    assert client.base_url == settings.OMNIPARSER_URL.rstrip("/")
    await client.close()
