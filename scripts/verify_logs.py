# scripts/verify_logs.py
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock
from app.engines.right_pupil import RightPupilEngine
from app.schemas.execution import AUIIR

async def main():
    print("[INFO] Starting RightPupilEngine Log Verification...")
    engine = RightPupilEngine()
    
    # Mock OmniClient to avoid network errors
    engine.omni_client.parse_screenshot = AsyncMock(return_value=[
        {"id": 1, "label": "button", "content": "Search"}
    ])
    
    # Mock SoMRenderer
    engine.som_renderer.draw_som = MagicMock(return_value=("base64_img", {1: {"label": "button"}}))
    
    # Mock Planner to return ONE action then STOP
    mock_action = AUIIR(
        action_type="click",
        target={"strategy": "visual", "value": "1", "description": "Search Button"}
    )
    
    # First call returns action, second call returns None (to stop loop)
    engine.planner.plan_next_step = AsyncMock(side_effect=[mock_action, None])
    
    # We also need to mock UiRunner.execute to actually run without a real browser if we want speed,
    # or let it fail but produce a log?
    # Actually, RightPupilEngine.start_session launches a real browser.
    # To keep this fast and robust, let's mock start_session/stop_session too?
    # No, we want to test the `finally` block in `run_task`.
    
    # Let's just mock the runner inside start_session? Hard to inject.
    # We will rely on real browser launch (headless) but mock the analysis.
    
    print("[INFO] Executing mocked task...")
    try:
        logs = await engine.run_task("Test Logs", "about:blank")
    except Exception as e:
        print(f"[WARN] Task raised exception: {e}")
        logs = [] # Should have been returned if handled
        
    print(f"[INFO] Task Finished. Log Count: {len(logs)}")
    
    if len(logs) > 0:
        print("[PASS] Logs captured successfully.")
        print(f"Sample Log: {logs[0]}")
        sys.exit(0)
    else:
        # If logs are empty, maybe runner.execute wasn't called or failed silently
        print("[FAIL] Logs are still empty!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
