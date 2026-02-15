import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.right_pupil.planner import VisualPlanner
from app.core.ai_client import AIModule, AIResponse
from app.schemas.aui_ir import VisualActionIR

@pytest.mark.asyncio
async def test_visual_planner_plan_next_step():
    """Verify VisualPlanner correctly invokes AI and parses response"""
    
    # Mock AI Manager
    mock_ai = AsyncMock()
    
    # Mock Response Content
    mock_response_content = json.dumps({
        "action_type": "click",
        "target": {
            "strategy": "visual",
            "value": "42",
            "description": "Submit Button"
        },
        "params": {},
        "expected_visual_change": "Form submitted"
    })
    
    mock_ai.invoke_vision.return_value = AIResponse(
        content=mock_response_content,
        model="mock-vision-model",
        usage={"total_tokens": 100},
        finish_reason="stop"
    )
    
    with patch("app.engines.right_pupil.planner.get_ai_manager", return_value=mock_ai):
        planner = VisualPlanner()
        
        # Test Data
        task = "Click the submit button"
        screenshot = "base64_image"
        som_text = "ID 42: Submit Button"
        history = []
        
        # Execution
        action = await planner.plan_next_step(task, screenshot, som_text, history)
        
        # Verification
        assert isinstance(action, VisualActionIR)
        assert action.action_type == "click"
        assert action.target.strategy == "visual"
        assert action.target.value == "42"
        
        # Verify AI Call
        mock_ai.invoke_vision.assert_called_once()
        call_args = mock_ai.invoke_vision.call_args
        assert call_args.kwargs["module"] == AIModule.RIGHT_PUPIL_GROUNDING
        assert "ID 42: Submit Button" in call_args.kwargs["prompt"]

@pytest.mark.asyncio
async def test_visual_planner_fallback():
    """Verify VisualPlanner fallback logic"""
    
    mock_ai = AsyncMock()
    mock_response_content = json.dumps({
        "action_type": "type",
        "target": {
            "strategy": "dom",
            "value": "#search",
            "description": "Search Box"
        },
        "params": {"text": "hello"},
        "expected_visual_change": "Text appears"
    })
    mock_ai.invoke_vision.return_value = AIResponse(
        content=mock_response_content,
        model="mock-vision-model",
        usage={"total_tokens": 100},
        finish_reason="stop"
    )
    
    with patch("app.engines.right_pupil.planner.get_ai_manager", return_value=mock_ai):
        planner = VisualPlanner()
        dom_tree = {"tag": "body", "children": []}
        
        action = await planner.plan_fallback_step("Type hello", dom_tree, "img")
        
        assert action.action_type == "type"
        assert action.target.strategy == "dom"
        assert action.target.value == "#search"
