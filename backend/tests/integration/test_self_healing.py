
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.right_pupil import RightPupilEngine
from app.schemas.aui_ir import VisualActionIR, VisualLocator

@pytest.mark.asyncio
async def test_locator_healing_loop():
    """
    Verify that RightPupilEngine switches to DOM strategy when Visual strategy fails.
    """
    # 1. Setup Engine with Mocks
    engine = RightPupilEngine()
    engine.start_session = AsyncMock() # Skip real browser start
    engine.stop_session = AsyncMock()
    engine.runner = AsyncMock()
    engine.omni_client = AsyncMock()
    engine.som_renderer = MagicMock()
    engine.som_renderer.draw_som.return_value = ("base64img", {})
    engine.dom_service = AsyncMock()
    engine.planner = AsyncMock()
    engine.page = AsyncMock()
    engine.waiter = AsyncMock()
    
    # Mock Page Screenshot
    engine.page.screenshot.return_value = b"fake_params"
    
    # Mock Omni Response (Empty for Locator Healing scenario - no popup)
    engine.omni_client.parse_screenshot.return_value = [] 
    
    # Mock Planner (Return a visual action first)
    visual_action = VisualActionIR(
        action_type="click", 
        target=VisualLocator(strategy="visual", value="1")
    )
    engine.planner.plan_next_step.side_effect = [
        visual_action,
        VisualActionIR(action_type="done", target=VisualLocator(strategy="visual", value="0"))
    ]
    
    # Mock Runner Execution
    # First call (Visual) -> Fail
    # Second call (Fallback DOM) -> Success
    engine.runner.execute.side_effect = [False, True] 
    
    # Mock Fallback Planner
    fallback_action = VisualActionIR(
        action_type="click", 
        target=VisualLocator(strategy="dom", value="#btn")
    )
    engine.planner.plan_fallback_step.return_value = fallback_action
    
    # 2. Run Task
    logs = await engine.run_task("Click button", "http://test.com")
    
    # 3. Verify
    # We verify that the runner was called twice.
    # 1. First call with Visual Strategy (which failed)
    # 2. Second call with DOM Strategy (which succeeded)
    assert engine.runner.execute.call_count == 2
    
    # Check arguments of the 2nd call (The Healed Action)
    call_args_list = engine.runner.execute.call_args_list
    second_call_args = call_args_list[1] # (args, kwargs)
    action_arg = second_call_args[0][0] # First arg is 'action'
    
    assert action_arg.target.strategy == "dom"
    assert action_arg.target.value == "#btn"
    
    # Verify fallback was called
    engine.planner.plan_fallback_step.assert_called_once()

@pytest.mark.asyncio
async def test_data_healing_loop():
    """
    Verify that RightPupilEngine regenerates data when Type action fails.
    """
    # 1. Setup
    engine = RightPupilEngine()
    engine.start_session = AsyncMock()
    engine.stop_session = AsyncMock()
    engine.runner = AsyncMock()
    engine.omni_client = AsyncMock()
    engine.som_renderer = MagicMock()
    engine.som_renderer.draw_som.return_value = ("base64img", {})
    engine.dom_service = AsyncMock()
    engine.planner = AsyncMock()
    engine.page = AsyncMock()
    engine.waiter = AsyncMock()
    engine.data_synthesizer = MagicMock() # Mock the synthesizer
    
    engine.page.screenshot.return_value = b"fake"
    engine.omni_client.parse_screenshot.return_value = []
    
    # Mock Planner: Type Action
    type_action = VisualActionIR(
        action_type="type", 
        target=VisualLocator(strategy="visual", value="50", description="email_field"),
        params={"text": "bad_email"}
    )
    engine.planner.plan_next_step.side_effect = [
        type_action, 
        VisualActionIR(action_type="done", target=VisualLocator(strategy="visual", value="0"))
    ]
    
    # Mock Runner: 
    # 1. Fail (Type with bad data)
    # 2. Success (Retry with new data)
    engine.runner.execute.side_effect = [False, True]
    
    # Mock Data Synthesizer
    engine.data_synthesizer.generate_value.return_value = "good@email.com"
    
    # 2. Run
    await engine.run_task("Enter email", "http://test.com")
    
    # 3. Verify
    assert engine.runner.execute.call_count == 2
    
    # Check 2nd call args
    call_args_list = engine.runner.execute.call_args_list
    second_call_args = call_args_list[1]
    executed_action_2 = second_call_args[0][0]
    
    # Should use the new value
    assert executed_action_2.params["text"] == "good@email.com"
    
    # Verify synthesizer was called
    engine.data_synthesizer.generate_value.assert_called_once()
    args, _ = engine.data_synthesizer.generate_value.call_args
    assert args[0] == "email_field" # field name hint

@pytest.mark.asyncio
async def test_environment_healing_popup():
    """
    Verify that RightPupilEngine closes popup when action fails.
    """
    # 1. Setup
    engine = RightPupilEngine()
    engine.start_session = AsyncMock()
    engine.stop_session = AsyncMock()
    engine.runner = AsyncMock()
    engine.omni_client = AsyncMock()
    engine.som_renderer = MagicMock()
    engine.dom_service = AsyncMock()
    engine.planner = AsyncMock()
    engine.page = AsyncMock()
    engine.waiter = AsyncMock()
    
    engine.page.screenshot.return_value = b"fake"
    
    # Mock Planner initial action
    visual_action = VisualActionIR(
        action_type="click", 
        target=VisualLocator(strategy="visual", value="10")
    )
    # Planner returns action, then 'done'
    engine.planner.plan_next_step.side_effect = [
        visual_action, 
        VisualActionIR(action_type="done", target=VisualLocator(strategy="visual", value="0"))
    ]
    
    # Mock Runner: 
    # 1. Fail (Visual Action blocked)
    # 2. Success (Closing Popup)
    # 3. Success (Retry Visual Action)
    engine.runner.execute.side_effect = [False, True, True]
    
    # Mock Omni for Environment Healing (Return a Close button)
    # First sense: Normal elements
    # Second sense (Healing): Contains "Close" button
    engine.omni_client.parse_screenshot.side_effect = [
        [], # Initial sense
        [{"label": "text", "content": "Close", "box_2d": [0,0,10,10], "ID": 99}] # Healing sense
    ]
    
    # Mock SoM for Healing to return ID map with "Close"
    def mock_draw_som(img, elements):
        # If elements has "Close", return ID 99
        if elements and "Close" in elements[0].get("content",""):
            # ID map format: {id: {label, content, ...}}
            return "base64", {99: {"label": "icon", "content": "Close"}}
        return "base64", {10: {"label": "btn"}}

    engine.som_renderer.draw_som.side_effect = mock_draw_som
    
    # 2. Run
    await engine.run_task("Click button", "http://test.com")
    
    # 3. Verify
    # Call args list of runner.execute
    # 1. Action(10) -> Fail
    # 2. Action(99) -> Success (Popup Close)
    # 3. Action(10) -> Success (Retry)
    assert engine.runner.execute.call_count == 3
    
    # Check 2nd call is closing popup (ID 99)
    call_args_list = engine.runner.execute.call_args_list
    second_call_args = call_args_list[1]
    executed_action_2 = second_call_args[0][0]
    assert executed_action_2.target.value == "99" 
    
    # Check 3rd call is retry (ID 10)
    third_call_args = call_args_list[2]
    executed_action_3 = third_call_args[0][0]
    assert executed_action_3.target.value == "10"

