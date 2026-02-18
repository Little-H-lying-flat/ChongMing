
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.engines.dispatcher import Dispatcher
from app.core.config import settings

async def verify_dispatcher_ui_logic():
    print("🚀 Verifying Dispatcher UI Logic...")
    
    # Mock Engines
    mock_left_pupil = AsyncMock()
    mock_right_pupil = AsyncMock()
    
    # Mock execute_step return
    mock_ui_result = {
        "success": True,
        "action_taken": "click",
        "target_description": "Search Button",
        "screenshot_before": "data:image/png;base64,fake_before",
        "screenshot_after": "data:image/png;base64,fake_after",
        "page_url": "https://example.com",
        "page_title": "Example Domain",
        "strategy": "ai_vision",
        "error": None
    }
    mock_right_pupil.execute_step.return_value = mock_ui_result
    
    # Initialize Dispatcher
    dispatcher = Dispatcher()
    dispatcher.left_pupil = mock_left_pupil
    dispatcher.right_pupil = mock_right_pupil
    
    # Test Step
    step = {
        "name": "Click Search",
        "description": "Click the search button",
        "step_type": "UI",
        "url": "https://example.com"
    }
    
    # Execute
    print("🔹 Executing UI Step via Dispatcher...")
    result = await dispatcher._execute_step(step, {}, 0)
    
    # Verify Call
    mock_right_pupil.execute_step.assert_called_once_with(
        "Click the search button", "https://example.com"
    )
    print("✅ Dispatcher correctly called right_pupil.execute_step")
    
    # Verify Result Structure
    print("🔹 Checking Result Structure...")
    assert result["success"] == True
    assert result["screenshot"] == "data:image/png;base64,fake_after"
    assert result["details"]["step_type"] == "UI"
    assert result["details"]["action_taken"] == "click"
    assert result["details"]["screenshot_before"] == "data:image/png;base64,fake_before"
    
    print("✅ Result structure matches expectation")
    print("🎉 Dispatcher UI Logic Verification Passed!")

if __name__ == "__main__":
    asyncio.run(verify_dispatcher_ui_logic())
