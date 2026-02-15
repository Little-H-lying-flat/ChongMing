import pytest
from unittest.mock import MagicMock, patch, call
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

@pytest.fixture
def mock_dispatcher_deps():
    """
    Setup mocks globally for execution_tasks imports.
    We patch where the class IS IMPORTED in execution_tasks or where it exists.
    Since execution_tasks uses local imports, we patch the source modules.
    """
    with patch("app.engines.runner.tc_loader.TestCaseLoader") as mock_loader, \
         patch("app.engines.right_pupil.RightPupilEngine") as mock_right_cls, \
         patch("app.engines.left_pupil.LeftPupilEngine") as mock_left_cls, \
         patch("app.services.execution_service.ExecutionService") as mock_exec_service:
         
        # 1. Setup Mock Engines
        mock_right = mock_right_cls.return_value
        mock_left = mock_left_cls.return_value
        
        # Custom Result Class to avoid MagicMock 'assert' attribute issues
        class MockResult:
            def __init__(self, success=True, status="passed", error=None):
                self.success = success
                self.status = status
                self.step_results = []
                self.total_duration_ms = 100
                self.screenshot = None
                self.screenshot_after = None # Required by Dispatcher
                self.error = error
                self.strategy_used = MagicMock()
                self.strategy_used.value = "visual"
                self.assertions_failed = [] # For API result
                self.response = MagicMock(status_code=200) # For API result

        # Async mocks for start/stop/execute
        async def async_success(*args, **kwargs):
            return MockResult(success=True, status="passed")

        async def async_failure(*args, **kwargs):
            return MockResult(success=False, status="failed", error="Mock Error")
            
        async def async_noop(*args, **kwargs):
            return None

        # Helper to set side effects dynamically
        mock_right.execute = MagicMock(side_effect=async_success)
        mock_right.start_session = MagicMock(side_effect=async_noop)
        mock_right.stop_session = MagicMock(side_effect=async_noop)
        
        mock_left.execute = MagicMock(side_effect=async_success)
        mock_left.__aenter__ = MagicMock(side_effect=async_noop)
        mock_left.__aexit__ = MagicMock(side_effect=async_noop)
        
        # 2. Setup ExecutionService (Async methods)
        mock_exec_service.create_execution = MagicMock(side_effect=async_noop)
        mock_exec_service.update_execution_status = MagicMock(side_effect=async_noop)
        mock_exec_service.create_step_result = MagicMock(side_effect=async_noop)
        
        yield {
            "loader": mock_loader,
            "right": mock_right,
            "left": mock_left,
            "service": mock_exec_service
        }

def test_flow3_happy_path_mixed_dispatch(mock_dispatcher_deps):
    """
    Flow 3 Scenario A: Happy Path (Mixed Mode)
    Verify Dispatcher calls RightPupil (Step 1) then LeftPupil (Step 2).
    """
    loader = mock_dispatcher_deps["loader"]
    right_engine = mock_dispatcher_deps["right"]
    left_engine = mock_dispatcher_deps["left"]
    exec_service = mock_dispatcher_deps["service"]
    
    # 1. Mock TC Loading
    steps = [
        {"type": "UI", "action": "click", "target": {"strategy": "visual"}},
        {"type": "API", "method": "GET", "url": "/test"}
    ]
    tc_ir = create_mock_tcir("TC_MIXED", ExecutionMode.HYBRID, steps)
    loader.load.return_value = tc_ir
    
    # 2. Run Task (Synchronously via apply)
    # Note: execute_test_cases creates its own loop via asyncio.run
    task_res = execute_test_cases.apply(args=[["TC_MIXED"]], kwargs={"config": {"parallel": False}})
    
    # 3. Assertions
    
    # Verify TC Loaded
    loader.load.assert_called_with("TC_MIXED")
    
    # Verify RightPupil called for Step 1
    assert right_engine.execute.call_count == 1
    # Check arg type if needed, but call_count is good
    
    # Verify LeftPupil called for Step 2
    assert left_engine.execute.call_count == 1
    
    # Verify ExecutionService usage
    # create_execution called once
    assert exec_service.create_execution.call_count == 1
    
    # create_step_result called once per Test Case (ExecutionStep table maps to TC)
    assert exec_service.create_step_result.call_count == 1
    
    # Verify the step results contain 2 steps
    step_call = exec_service.create_step_result.call_args
    args, _ = step_call
    # args: (execution_id, tc_id, status, result_dict, duration, error)
    result_dict = args[3]
    assert "steps" in result_dict
    assert len(result_dict["steps"]) == 2 # 2 internal steps passed
    # Args: (execution_id, status, summary, duration)
    update_call = exec_service.update_execution_status.call_args
    assert update_call is not None
    args, _ = update_call
    assert args[1] == ExecutionStatus.PASSED # Status is 2nd arg
    assert args[2]["passed"] == 1
    assert args[2]["failed"] == 0


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
        {"type": "UI", "action": "click"}, # Will Fail
        {"type": "API", "method": "GET"}   # Should Skip
    ]
    tc_ir = create_mock_tcir("TC_FAIL", ExecutionMode.HYBRID, steps)
    loader.load.return_value = tc_ir
    
    # 2. Configure Right Engine to Fail
    async def async_fail(*args, **kwargs):
        res = MagicMock()
        res.success = False
        res.status = "failed"
        res.step_results = []
        res.total_duration_ms = 50
        res.error = "Simulated UI Failure"
        res.screenshot = None
        # Start/End strategy val
        res.strategy_used.value = "visual"
        return res
    right_engine.execute.side_effect = async_fail
    
    # 3. Run Task
    result = execute_test_cases.apply(args=[["TC_FAIL"]], kwargs={"config": {"parallel": False}})
    
    # 4. Assertions
    
    # Verify RightPupil called (Step 1)
    assert right_engine.execute.call_count == 1
    
    # Verify LeftPupil NOT called (Step 2 Skipped)
    assert left_engine.execute.call_count == 0
    
    # Verify DB Logic
    # One step result (Failed)
    assert exec_service.create_step_result.call_count == 1
    step_call = exec_service.create_step_result.call_args
    args, _ = step_call
    # args: (execution_id, tc_id, status, result_dict, width?, error?) 
    # Check signature in execution_tasks: (execution_id, tc_id, status, result, duration, error)
    assert args[2] == ExecutionStatus.FAILED 
    
    # Verify Final Status FAILED
    update_call = exec_service.update_execution_status.call_args
    args, _ = update_call
    assert args[1] == ExecutionStatus.FAILED
    assert args[2]["failed"] == 1
