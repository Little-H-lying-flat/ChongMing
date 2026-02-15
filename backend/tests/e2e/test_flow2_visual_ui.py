import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.right_pupil import RightPupilEngine
from app.schemas.aui_ir import VisualActionIR, VisualLocator

@pytest.fixture
def mock_engine_deps():
    """
    Setup mocks for RightPupilEngine dependencies
    """
    with patch("app.engines.right_pupil.async_playwright") as mock_pw, \
         patch("app.engines.right_pupil.OmniClient") as mock_omni_cls, \
         patch("app.engines.right_pupil.SoMRenderer") as mock_som_cls, \
         patch("app.engines.right_pupil.VisualPlanner") as mock_planner_cls, \
         patch("app.engines.right_pupil.UiRunner") as mock_runner_cls, \
         patch("app.engines.right_pupil.DataSynthesizer") as mock_synth, \
         patch("app.engines.right_pupil.SmartWaiter") as mock_waiter:
         
        # 1. Mock Playwright internals
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        async def async_start(*args, **kwargs):
            pw = MagicMock()
            pw.chromium.launch.side_effect = async_launch
            pw.stop.side_effect = async_close
            return pw
            
        async def async_launch(*args, **kwargs):
            return mock_browser
            
        async def async_new_context(*args, **kwargs):
            return mock_context
            
        async def async_new_page(*args, **kwargs):
            return mock_page
            
        async def async_goto(*args, **kwargs):
            return None
            
        async def async_screenshot(*args, **kwargs):
            return b"fake_screenshot_bytes"

        async def async_close(*args, **kwargs):
            return None
            
        # Bind async methods to mocks
        mock_pw.return_value.start.side_effect = async_start
        mock_browser.new_context.side_effect = async_new_context
        mock_browser.close.side_effect = async_close
        mock_context.new_page.side_effect = async_new_page
        mock_context.close.side_effect = async_close
        mock_page.goto.side_effect = async_goto
        mock_page.screenshot.side_effect = async_screenshot
        
        # 2. Mock OmniClient
        mock_omni = mock_omni_cls.return_value
        async def default_parse(*args, **kwargs):
            return []
        mock_omni.parse_screenshot = MagicMock(side_effect=default_parse)
        
        # 3. Mock SoMRenderer
        mock_som = mock_som_cls.return_value
        mock_som.draw_som = MagicMock() # Sync
        
        # 4. Mock VisualPlanner
        mock_planner = mock_planner_cls.return_value
        async def default_plan(*args, **kwargs):
            return None
        mock_planner.plan_next_step = MagicMock(side_effect=default_plan)
        
        # 5. Mock UiRunner
        mock_runner = mock_runner_cls.return_value
        async def default_execute(*args, **kwargs):
            return True
        mock_runner.execute = MagicMock(side_effect=default_execute)
        
        # 6. Mock SmartWaiter
        mock_waiter_instance = mock_waiter.return_value
        async def default_wait(*args, **kwargs):
            return True
        mock_waiter_instance.wait_until_stable = MagicMock(side_effect=default_wait)
        
        yield {
            "page": mock_page,
            "omni": mock_omni,
            "som": mock_som,
            "planner": mock_planner,
            "runner": mock_runner,
            "waiter": mock_waiter_instance
        }

@pytest.mark.asyncio
async def test_flow2_happy_path(mock_engine_deps):
    """
    Flow 2: Visual UI Automation (Adhoc) - Happy Path
    
    Steps:
    1. Init Session (Mocked Browser)
    2. Navigate to URL
    3. Capture Screenshot -> OmniParser (Mocked 2 boxes) -> SoM Render
    4. Plan Next Step (Mocked 'Click ID 1')
    5. Execute Action (Mocked UiRunner)
    6. Loop -> Plan 'Done' -> Exit
    """
    # --- Setup Mocks ---
    mock_omni = mock_engine_deps["omni"]
    mock_som = mock_engine_deps["som"]
    mock_planner = mock_engine_deps["planner"]
    mock_runner = mock_engine_deps["runner"]
    mock_page = mock_engine_deps["page"]
    
    # Mock Screenshot (return bytes)
    mock_page.screenshot.return_value = b"fake_screenshot_bytes"
    
    # Mock OmniParser Return (2 Elements)
    async def mock_parse(*args, **kwargs):
        return [
            {"label": "button", "content": "Search", "box_2d": [10, 10, 100, 50]},
            {"label": "input", "content": "", "box_2d": [10, 60, 200, 90]}
        ]
    mock_omni.parse_screenshot.side_effect = mock_parse
    
    # Mock SoMRenderer Return (Annotated Base64, ID Map)
    id_map_mock = {
        1: {"label": "button", "content": "Search", "center": (55, 30)},
        2: {"label": "input", "content": "", "center": (105, 75)}
    }
    mock_som.draw_som.return_value = ("annotated_base64_str", id_map_mock)
    
    # Mock Planner (Sequence: Click -> Done)
    action_click = VisualActionIR(
        id="step_1",
        action_type="click",
        target=VisualLocator(strategy="visual", value="1")
    )
    action_done = VisualActionIR(
        id="step_2",
        action_type="done",
        target=None
    )
    
    async def return_click(*args, **kwargs): return action_click
    async def return_done(*args, **kwargs): return action_done
    
    # Note: side_effect iterable must return the return value of the call.
    # Since we await the call, it must return a coroutine.
    mock_planner.plan_next_step.side_effect = [return_click(), return_done()]
    
    # Mock Runner success
    async def return_true(*args, **kwargs): return True
    mock_runner.execute.side_effect = return_true
    
    # --- Execute SUT ---
    engine = RightPupilEngine()
    logs = await engine.run_task(prompt="Click the search button", url="http://test.com")
    
    # --- Assertions ---
    
    # 1. Verify Navigation
    # Check goto called (it returns a coroutine, so we can't assert_awaited_once_with on MagicMock easily if we replaced start)
    # But mock_page.goto IS a MagicMock with side_effect=async_goto.
    # verifying call args is enough.
    mock_page.goto.assert_called_with("http://test.com")
    
    # 2. Verify OmniParser Usage
    mock_omni.parse_screenshot.assert_called()
    
    # 3. Verify SoM Renderer Usage
    # mock_som.draw_som is a synchronous method run in executor.
    mock_som.draw_som.assert_called()
    
    # 4. Verify VisualPlanner Usage
    # Check 1st call args (Prompt, Base64, SoM Text) - Positional Args
    call_args = mock_planner.plan_next_step.call_args_list[0]
    assert call_args.args[0] == "Click the search button" # Task is 1st arg
    assert "annotated_base64_str" in call_args.args[1]    # Screenshot is 2nd arg
    assert "ID 1: button Search" in call_args.args[2]     # SoM Text is 3rd arg
    
    # 5. Verify UiRunner Usage (The Critical "Limb" Check)
    # Must be called with the action returned by Planner and the ID Map from SoM
    mock_runner.execute.assert_called_with(action_click, id_map_mock)
    
    # 6. Verify Stop Session
    pass 

@pytest.mark.asyncio
async def test_flow2_omniparser_error(mock_engine_deps):
    """
    Flow 2 Error Path: OmniParser Service Down
    
    Expectation: Engine should handle error gracefully and stop execution.
    """
    mock_omni = mock_engine_deps["omni"]
    mock_page = mock_engine_deps["page"]
    mock_planner = mock_engine_deps["planner"]
    
    # Mock Screenshot
    mock_page.screenshot.return_value = b"fake_screenshot_bytes"
    
    # Mock OmniParser Failure (Use async wrapper to avoid AsyncMock await issues)
    async def raise_error(*args, **kwargs):
        raise Exception("OmniParser Connection Refused")
    
    mock_omni.parse_screenshot.side_effect = raise_error
    
    # --- Execute SUT ---
    engine = RightPupilEngine()
    logs = await engine.run_task(prompt="Click search", url="http://test.com")
    
    # --- Assertions ---
    
    # 1. Verify Navigation
    mock_page.goto.assert_called_with("http://test.com")
    
    # 2. Verify OmniParser Caleld
    mock_omni.parse_screenshot.assert_called_once()
    
    # 3. Verify Planner NOT called (loop broke)
    mock_planner.plan_next_step.assert_not_called()
