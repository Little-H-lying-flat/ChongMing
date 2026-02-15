
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.right_pupil import RightPupilEngine
from app.schemas.execution import AUIIR, ActionType

@pytest.fixture
def mock_dependencies():
    with patch("app.engines.right_pupil.async_playwright") as mock_pw, \
         patch("app.engines.right_pupil.OmniClient") as mock_omni, \
         patch("app.engines.right_pupil.SoMRenderer") as mock_som, \
         patch("app.engines.right_pupil.DomService") as mock_dom, \
         patch("app.engines.right_pupil.VisualPlanner") as mock_planner, \
         patch("app.engines.right_pupil.UiRunner") as mock_runner_cls, \
         patch("app.engines.right_pupil.SmartWaiter") as mock_waiter:
        
        # Setup Playwright mocks
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_pw.return_value.start.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Setup Runner mock instance
        mock_runner_instance = AsyncMock()
        mock_runner_cls.return_value = mock_runner_instance
        
        yield {
            "pw": mock_pw,
            "browser": mock_browser,
            "page": mock_page,
            "runner": mock_runner_instance,
            "omni": mock_omni,
            "som": mock_som
        }

@pytest.mark.asyncio
async def test_right_pupil_lifecycle(mock_dependencies):
    """Test start and stop session"""
    engine = RightPupilEngine()
    
    await engine.start_session(headless=True)
    
    # Verify Playwright started
    mock_dependencies["pw"].return_value.start.assert_called_once()
    mock_dependencies["browser"].new_context.assert_called_once()
    
    assert engine.page is not None
    assert engine.runner is not None
    
    await engine.stop_session()
    
    mock_dependencies["browser"].close.assert_called_once()
    assert engine.runner is None

@pytest.mark.asyncio
async def test_right_pupil_execute_success(mock_dependencies):
    """Test executing a single action successfully"""
    engine = RightPupilEngine()
    await engine.start_session(headless=True)
    
    # Mock runner execute success
    mock_dependencies["runner"].execute.return_value = True
    
    action = AUIIR(
        action_type=ActionType.CLICK,
        target={"strategy": "css", "selector": "#btn"}
    )
    
    result = await engine.execute(action)
    
    assert result.success is True
    assert result.error is None
    # Verify runner was called with empty id_map (as per current impl)
    mock_dependencies["runner"].execute.assert_called_once_with(action, id_map={})

@pytest.mark.asyncio
async def test_right_pupil_execute_failure(mock_dependencies):
    """Test executing a single action with failure"""
    engine = RightPupilEngine()
    await engine.start_session(headless=True)
    
    # Mock runner execute failure exception
    mock_dependencies["runner"].execute.side_effect = Exception("Element not found")
    
    action = AUIIR(
        action_type=ActionType.CLICK,
        target={"strategy": "css", "selector": "#btn"}
    )
    
    result = await engine.execute(action)
    
    assert result.success is False
    assert "Element not found" in result.error
