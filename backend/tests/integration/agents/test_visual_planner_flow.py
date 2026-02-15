
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.right_pupil import RightPupilEngine
from app.core.ai_client import AIResponse
from app.schemas.execution import AUIIR

@pytest.fixture
def mock_engine_deps():
    with patch("app.engines.right_pupil.async_playwright") as mock_pw, \
         patch("app.engines.right_pupil.OmniClient") as mock_omni, \
         patch("app.engines.right_pupil.SoMRenderer") as mock_som, \
         patch("app.engines.right_pupil.DomService") as mock_dom, \
         patch("app.engines.right_pupil.UiRunner") as mock_runner_cls, \
         patch("app.engines.right_pupil.SmartWaiter") as mock_waiter, \
         patch("app.engines.right_pupil.planner.get_ai_manager") as mock_get_ai:
        
        # Setup Browser mocks (to pass start_session)
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        # Setup Waiter
        mock_waiter_instance = mock_waiter.return_value
        mock_waiter_instance.wait_until_stable = AsyncMock()

        
        # async_playwright().start() is async
        mock_pw_context_manager = mock_pw.return_value
        mock_pw_context_manager.start = AsyncMock()
        mock_pw_context_manager.start.return_value.chromium.launch.return_value = mock_browser
        
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.screenshot = AsyncMock(return_value=b"fake_png")
        
        # Setup Runner
        mock_runner_instance = AsyncMock()
        mock_runner_cls.return_value = mock_runner_instance
        # Mock successful execution with side effect to update logs
        mock_runner_instance.trace_logs = []
        
        async def execute_side_effect(action, id_map):
            mock_runner_instance.trace_logs.append({
                "status": "success", 
                "action": action.model_dump() if hasattr(action, 'model_dump') else action
            })
            return True
            
        mock_runner_instance.execute.side_effect = execute_side_effect


        # Setup Omni & SoM
        mock_omni_inst = mock_omni.return_value
        mock_omni_inst.parse_screenshot = AsyncMock(return_value=[{"label": "button"}])
        
        mock_som_inst = mock_som.return_value
        mock_som_inst.draw_som.return_value = ("base64img", {1: {"label": "btn", "content": "Submit"}})
        
        # Setup AI Manager (The Brain)
        mock_ai_manager = AsyncMock()
        mock_get_ai.return_value = mock_ai_manager
        
        yield {
            "ai_manager": mock_ai_manager,
            "runner": mock_runner_instance,
            "page": mock_page
        }

@pytest.mark.asyncio
async def test_visual_planner_flow(mock_engine_deps):
    """
    Test Integration: VisualPlanner (Brain) -> RightPupilEngine (Limb)
    1. Mock AI returns "Click {selector}"
    2. Engine should parse this and call Runner.execute
    """
    
    # 1. Prepare Mock LLM Response (The "Brain" decision)
    # We simulate the LLM deciding to click a button
    llm_decision_json = """
    ```json
    {
        "action_type": "click",
        "target": {
            "strategy": "visual",
            "value": "1",
            "description": "Submit Button"
        },
        "params": {},
        "expected_visual_change": "Form submitted"
    }
    ```
    """
    
    mock_engine_deps["ai_manager"].invoke_vision.return_value = AIResponse(
        content=llm_decision_json,
        model="qwen-vl-max",
        usage={"total_tokens": 100},
        finish_reason="stop"
    )
    
    # 2. Run Engine (The "Body")
    engine = RightPupilEngine()
    # Limit max steps to 1 to run a single loop iteration
    engine.max_steps = 1
    
    history = await engine.run_task("Click submit", "http://test.com")
    
    # 3. Assertions
    
    # Assert Brain was consulted
    mock_engine_deps["ai_manager"].invoke_vision.assert_called_once()
    
    # Assert Limb was moved (Runner executed the action)
    # We check if execute was called with an AUIIR matching our LLM output
    mock_engine_deps["runner"].execute.assert_called()
    
    call_args = mock_engine_deps["runner"].execute.call_args
    action_arg = call_args[0][0] # First arg is 'action'
    
    assert isinstance(action_arg, AUIIR)
    assert action_arg.action_type == "click"
    assert action_arg.target.value == "1"
    
    # Assert History recorded success
    assert len(history) == 1
    assert history[0]["status"] == "success"
    assert history[0]["action"]["action_type"] == "click"
