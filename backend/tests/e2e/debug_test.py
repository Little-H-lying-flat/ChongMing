import asyncio
from unittest.mock import MagicMock
from app.engines.dispatcher import Dispatcher
from app.schemas.execution import ExecutionMode

async def run_debug():
    dispatcher = Dispatcher()
    
    # Mock Right (UI)
    right = MagicMock()
    right.execute_step = MagicMock(side_effect=lambda *a, **kw: {"status": "success", "screenshot_after": "base64", "duration_ms": 100})
    dispatcher.right_pupil = right
    
    # Mock Left (API)
    left = MagicMock()
    left.execute = MagicMock(side_effect=lambda *a, **kw: MagicMock(success=True, status="passed", response=MagicMock(status_code=200)))
    dispatcher.left_pupil = left
    
    # Create steps exactly like in the test
    steps = [
        {"type": "UI", "action": "click", "target": {"strategy": "visual"}},
        {"type": "API", "id": "step_2", "method": "GET", "url": "/test"}
    ]
    
    for i, step in enumerate(steps):
        try:
            print(f"Executing Step {i+1}: {step}")
            res = await dispatcher._execute_step(step, ExecutionMode.HYBRID)
            print(f"Step {i+1} Result: {res.get('status')}")
        except Exception as e:
            print(f"Step {i+1} Exception:", repr(e))

asyncio.run(run_debug())
