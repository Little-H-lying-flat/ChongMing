
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.right_pupil import RightPupilEngine


@pytest.fixture
def mock_dependencies():
    with patch("app.engines.right_pupil.async_playwright") as mock_pw, \
         patch("app.engines.right_pupil.OmniClient") as mock_omni, \
         patch("app.engines.right_pupil.SoMRenderer") as mock_som, \
         patch("app.engines.right_pupil.DomService") as mock_dom, \
         patch("app.engines.right_pupil.VisualPlanner") as mock_planner, \
         patch("app.engines.right_pupil.UiRunner") as mock_runner_cls, \
         patch("app.engines.right_pupil.SmartWaiter") as mock_waiter, \
         patch("app.engines.right_pupil.Stealth") as mock_stealth:
        
        # Setup Playwright async chain: async_playwright() -> .start() -> .chromium.launch() -> browser
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        # async_playwright() returns an object whose .start() is a coroutine returning the pw instance
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.start = AsyncMock(return_value=mock_pw_instance)
        
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # Mock page properties
        mock_page.url = "http://localhost/test"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.screenshot = AsyncMock(return_value=b"fake_png_bytes")
        mock_page.goto = AsyncMock()
        
        # Stealth mock
        mock_stealth_instance = MagicMock()
        mock_stealth_instance.apply_stealth_async = AsyncMock()
        mock_stealth.return_value = mock_stealth_instance
        
        # Setup Runner mock instance
        mock_runner_instance = AsyncMock()
        mock_runner_cls.return_value = mock_runner_instance
        
        # SmartWaiter mock
        mock_waiter_instance = AsyncMock()
        mock_waiter.return_value = mock_waiter_instance
        
        yield {
            "pw": mock_pw,
            "pw_instance": mock_pw_instance,
            "browser": mock_browser,
            "context": mock_context,
            "page": mock_page,
            "runner": mock_runner_instance,
            "omni": mock_omni,
            "som": mock_som,
            "planner": mock_planner,
            "stealth": mock_stealth,
        }

@pytest.mark.asyncio
async def test_right_pupil_lifecycle(mock_dependencies):
    """Test start and stop session lifecycle"""
    engine = RightPupilEngine()
    
    await engine.start_session(headless=True)
    
    # Verify Playwright started
    mock_dependencies["pw"].return_value.start.assert_called_once()
    mock_dependencies["pw_instance"].chromium.launch.assert_called_once()
    mock_dependencies["browser"].new_context.assert_called_once()
    
    assert engine.page is not None
    assert engine.runner is not None
    
    await engine.stop_session()
    
    mock_dependencies["browser"].close.assert_called_once()
    assert engine.runner is None

@pytest.mark.asyncio
async def test_right_pupil_execute_step_navigate(mock_dependencies):
    """Test execute_step with URL navigation (pure goto)"""
    engine = RightPupilEngine()
    await engine.start_session(headless=True)
    
    result = await engine.execute_step(
        description="Navigate to login page",
        url="http://localhost/login",
        execution_id="exec-001"
    )
    
    assert result["success"] is True
    assert result["action_taken"] == "navigate"
    mock_dependencies["page"].goto.assert_called_once()

@pytest.mark.asyncio
async def test_right_pupil_execute_step_no_session(mock_dependencies):
    """Test execute_step raises error without active session"""
    engine = RightPupilEngine()
    # Don't call start_session
    
    with pytest.raises(RuntimeError, match="Session not started"):
        await engine.execute_step(description="Click login button")
