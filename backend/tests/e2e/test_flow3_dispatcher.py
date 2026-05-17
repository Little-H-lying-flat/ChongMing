import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from app.tasks.execution_tasks import execute_test_cases
from app.schemas.execution import TCIR, ExecutionMode, StepResult as SchemaStepResult
from app.models.execution import ExecutionStatus
from app.engines.right_pupil import RightPupilEngine
from app.engines.left_pupil import LeftPupilEngine
import asyncio

# --- Mock Data ---
def create_mock_tcir(tc_id, mode, steps):
    return TCIR(
        id=tc_id,
        name="Mock TC",
        mode=mode,
        steps=steps
    )

class AsyncContextManagerMock(MagicMock):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

@pytest.fixture
def mock_dispatcher_deps():
    """
    Setup mocks globally for execution_tasks imports.
    
    Key insight: execution_tasks.py imports ExecutionService INSIDE the function body
    and calls its methods as CLASS-LEVEL static methods, e.g.:
        ExecutionService.update_execution_status(...)
        ExecutionService.create_step_result(...)
    So we must patch the class and set up AsyncMock on the class-level attributes.
    """
    with patch("app.engines.runner.tc_loader.TestCaseLoader") as mock_loader, \
         patch("app.engines.right_pupil.RightPupilEngine", new_callable=AsyncContextManagerMock) as mock_right_cls, \
         patch("app.engines.left_pupil.LeftPupilEngine", new_callable=AsyncContextManagerMock) as mock_left_cls, \
         patch("app.services.execution_service.ExecutionService") as mock_exec_service:
         
        # 1. Setup Mock Engines using AsyncContextManagerMock
        mock_right = mock_right_cls.return_value
        mock_left = mock_left_cls.return_value
        
        # Right Pupil (UI) Mock
        async def right_async_success(*args, **kwargs):
            return {
                "success": True,
                "status": "success",
                "screenshot_after": "fake_base64_data",
                "screenshot_before": "fake_base64_data",
                "duration_ms": 100,
                "page_url": "http://localhost",
                "page_title": "Test Page",
                "strategy": "visual"
            }
        
        mock_right.execute_step.side_effect = right_async_success
        mock_right.start_session = AsyncMock()
        mock_right.stop_session = AsyncMock()
        
        # Left Pupil (API) Mock
        class LeftMockResult:
            def __init__(self, success=True, status="passed"):
                self.success = success
                self.status = status
                self.response = MagicMock(
                    status_code=200, 
                    request_url="/test", 
                    request_method="GET",
                    headers={"Content-Type": "application/json"},
                    body="{}"
                )
                self.total_duration_ms = 100
                self.error = None
                self.assertions_failed = []
                self.extracted_values = {}
                
        async def left_async_success(*args, **kwargs):
            return LeftMockResult(success=True)
            
        mock_left.execute.side_effect = left_async_success
        
        # 2. Setup ExecutionService — these are STATIC/CLASS methods
        #    The production code calls e.g. ExecutionService.update_execution_status(...)
        #    So we set AsyncMock directly on the class mock's attributes.
        mock_exec_service.update_execution_status = AsyncMock(return_value=None)
        mock_exec_service.create_step_result = AsyncMock(return_value=None)
        
        yield {
            "loader": mock_loader,
            "right": mock_right,
            "left": mock_left,
            "service": mock_exec_service
        }

def test_flow3_happy_path_mixed_dispatch(mock_dispatcher_deps):
    """
    Flow 3 Scenario A: Happy Path (Mixed Mode)
    - Step 1 (UI) succeeds via RightPupilEngine
    - Step 2 (API) succeeds via LeftPupilEngine
    - Final status: PASSED
    """
    loader = mock_dispatcher_deps["loader"]
    right_engine = mock_dispatcher_deps["right"]
    left_engine = mock_dispatcher_deps["left"]
    exec_service = mock_dispatcher_deps["service"]
    
    # 1. Mock TC Loading
    steps = [
        {"type": "UI", "id": "step_1", "action": "click", "target": {"strategy": "visual"}},
        {"type": "API", "id": "step_2", "method": "GET", "url": "/test"}
    ]
    tc_ir = create_mock_tcir("TC_MIXED", ExecutionMode.HYBRID, steps)
    loader.load.return_value = tc_ir
    
    # 2. Run Task 
    task_res = execute_test_cases.apply(args=["mock-exec-1", ["TC_MIXED"]], kwargs={"config": {"parallel": False}})
    
    # 3. Assertions
    loader.load.assert_called_with("TC_MIXED")
    
    # Verify RightPupil called for UI Step 1
    assert right_engine.execute_step.call_count == 1
    
    # Verify LeftPupil called for API Step 2
    assert left_engine.execute.call_count == 1
    
    # Verify create_step_result was called (persists the TC result)
    assert exec_service.create_step_result.call_count == 1
    
    # Verify the step results contain 2 steps
    step_call = exec_service.create_step_result.call_args
    args, _ = step_call
    result_dict = args[3]  # 4th positional arg is the result dict
    assert "steps" in result_dict
    assert len(result_dict["steps"]) == 2 
    
    # Verify Final Status PASSED via update_execution_status
    update_call = exec_service.update_execution_status.call_args
    assert update_call is not None
    args, _ = update_call
    assert args[1] == ExecutionStatus.PASSED 
    assert args[2]["passed"] == 1
    assert args[2]["failed"] == 0


def test_flow3_nested_only_api_step_reaches_left_pupil_with_flat_api_ir(mock_dispatcher_deps):
    loader = mock_dispatcher_deps["loader"]
    left_engine = mock_dispatcher_deps["left"]
    exec_service = mock_dispatcher_deps["service"]

    steps = [
        {
            "id": "STEP_NESTED",
            "step_type": "API",
            "name": "Nested API",
            "request": {
                "method": "GET",
                "url": "http://example.test/ping",
                "headers": {"X-Test": "1"},
            },
            "assertion": {
                "status_code": 200,
                "json_assertions": {"$.pong": True},
            },
            "extraction": {"pong": "$.pong"},
        }
    ]
    tc_ir = create_mock_tcir("TC_NESTED_API", ExecutionMode.API, steps)
    loader.load.return_value = tc_ir

    execute_test_cases.apply(args=["mock-exec-nested", ["TC_NESTED_API"]], kwargs={"config": {"parallel": False}})

    assert left_engine.execute.call_count == 1
    api_ir = left_engine.execute.call_args.args[0]
    assert api_ir.method == "GET"
    assert api_ir.url == "http://example.test/ping"
    assert api_ir.expected_status_code == 200
    assert api_ir.json_assertions == {"$.pong": True}
    assert api_ir.extract == {"pong": "$.pong"}
    assert exec_service.create_step_result.call_count == 1


def test_flow3_error_path_circuit_breaker(mock_dispatcher_deps):
    """
    Flow 3 Scenario B: Error Path
    Step 1 (UI) fails -> Stop -> Step 2 skipped -> Status FAILED
    """
    loader = mock_dispatcher_deps["loader"]
    right_engine = mock_dispatcher_deps["right"]
    left_engine = mock_dispatcher_deps["left"]
    exec_service = mock_dispatcher_deps["service"]
    
    # 1. Mock TC
    steps = [
        {"type": "UI", "id": "step_1", "action": "click"}, # Will Fail
        {"type": "API", "id": "step_2", "method": "GET"}   # Should Skip
    ]
    tc_ir = create_mock_tcir("TC_FAIL", ExecutionMode.HYBRID, steps)
    loader.load.return_value = tc_ir
    
    # 2. Configure Right Engine to Fail
    async def right_async_fail(*args, **kwargs):
        return {
            "status": "failed", 
            "error": "UI Error", 
            "duration_ms": 50,
            "screenshot_after": None,
            "screenshot_before": None
        }
    right_engine.execute_step.side_effect = right_async_fail
    
    # 3. Run Task
    result = execute_test_cases.apply(args=["mock-exec-2", ["TC_FAIL"]], kwargs={"config": {"parallel": False}})
    
    # 4. Assertions
    assert right_engine.execute_step.call_count == 1
    assert left_engine.execute.call_count == 0
    
    # Verify DB Logic — step result persisted as FAILED
    assert exec_service.create_step_result.call_count == 1
    step_call = exec_service.create_step_result.call_args
    args, _ = step_call
    assert args[2] == ExecutionStatus.FAILED 
    
    # Verify Final Status FAILED
    update_call = exec_service.update_execution_status.call_args
    args, _ = update_call
    assert args[1] == ExecutionStatus.FAILED
    assert args[2]["failed"] == 1
