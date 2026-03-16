
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from app.engines.right_pupil import RightPupilEngine
from app.schemas.execution import AUIIR
from app.schemas.aui_ir import VisualLocator


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


def test_bootstrap_navigation_only_on_first_cycle():
    state_first = {"task_url": "https://example.com", "action_intent": None, "history": []}
    state_with_history = {
        "task_url": "https://example.com",
        "action_intent": None,
        "history": [{"action": "navigate"}],
    }
    state_with_intent = {
        "task_url": "https://example.com",
        "action_intent": object(),
        "history": [],
    }

    assert RightPupilEngine._should_bootstrap_navigation(state_first) is True
    assert RightPupilEngine._should_bootstrap_navigation(state_with_history) is False
    assert RightPupilEngine._should_bootstrap_navigation(state_with_intent) is False


@pytest.mark.asyncio
async def test_node_evaluate_detects_cross_domain_hijack(mock_dependencies):
    engine = RightPupilEngine()
    await engine.start_session(headless=True)
    mock_dependencies["page"].url = "https://ads.example.net/popup"

    action = AUIIR(
        action_type="click",
        target=VisualLocator(strategy="dom", value="#login-btn"),
        params={},
    )
    state = {
        "action_result": {"success": True},
        "action_intent": action,
        "task_url": "https://www.saucedemo.com",
        "history": [],
        "error": None,
    }
    result = await engine.node_evaluate(state)

    assert result["failure_type"] == "ENVIRONMENT_ISSUE"
    assert "cross-domain" in result["error"].lower()


def test_action_correction_handles_missing_params_and_infers_text(mock_dependencies):
    engine = RightPupilEngine()
    action = AUIIR(
        action_type="click",
        target=VisualLocator(strategy="dom", value="#username"),
        params={},
    )
    action.params = None

    corrected = engine._correct_action_type(action, "请在用户名输入 admin")
    assert corrected.action_type == "type"
    assert corrected.params.get("text") == "admin"


def test_failure_classifier_heuristic():
    assert RightPupilEngine._classify_failure_heuristic("Unexpected cross-domain navigation") == "ENVIRONMENT_ISSUE"
    assert RightPupilEngine._classify_failure_heuristic("Perception Error: OmniParser timeout") == "VISION_FAILED"
    assert RightPupilEngine._classify_failure_heuristic("Execution Error: timeout 30s") == "RETRYABLE"


def test_extract_semantic_hint_for_click_targets():
    assert RightPupilEngine._extract_semantic_hint("Click Add to cart for Sauce Labs Backpack") == "Sauce Labs Backpack"
    assert RightPupilEngine._extract_semantic_hint('Click the item named "Quarter Zip Jacket"') == "Quarter Zip Jacket"
    assert RightPupilEngine._extract_semantic_hint("Click the Login button") is None


def test_enrich_action_context_adds_semantic_hint(mock_dependencies):
    engine = RightPupilEngine()
    action = AUIIR(
        action_type="click",
        target=VisualLocator(strategy="visual", value="47"),
        params={},
    )

    enriched = engine._enrich_action_context(action, "Click Add to cart for Sauce Labs Backpack")

    assert enriched.params["semantic_hint"] == "Sauce Labs Backpack"


def test_extract_field_hint_for_type_targets():
    assert RightPupilEngine._extract_field_hint("Type Codex into the First Name input") == "First Name"
    assert RightPupilEngine._extract_field_hint("Fill data in the Postal Code field") == "Postal Code"
    assert RightPupilEngine._extract_field_hint("Type hello") is None


def test_enrich_action_context_adds_field_hint_for_type(mock_dependencies):
    engine = RightPupilEngine()
    action = AUIIR(
        action_type="type",
        target=VisualLocator(strategy="visual", value="21"),
        params={"text": "Codex"},
    )

    enriched = engine._enrich_action_context(action, "Type Codex into the First Name input")

    assert enriched.params["field_hint"] == "First Name"
    assert enriched.params["semantic_hint"] == "First Name"


@pytest.mark.asyncio
async def test_node_evaluate_rejects_type_when_value_not_persisted(mock_dependencies):
    engine = RightPupilEngine()
    await engine.start_session(headless=True)
    mock_dependencies["page"].url = "https://www.saucedemo.com/checkout-step-one.html"
    mock_dependencies["runner"].trace_logs = [
        {
            "coords": {"x": 120, "y": 240},
            "input_resolution": {"x": 125, "y": 245, "score": 299},
        }
    ]
    engine._read_input_value_by_hint = AsyncMock(
        return_value={"value": "", "matched_by": "hint"}
    )

    action = AUIIR(
        action_type="type",
        target=VisualLocator(strategy="visual", value="21"),
        params={"text": "Codex", "field_hint": "First Name"},
    )
    state = {
        "action_result": {"success": True},
        "action_intent": action,
        "task_url": "https://www.saucedemo.com",
        "history": [],
        "error": None,
    }

    result = await engine.node_evaluate(state)

    assert result["failure_type"] == "RETRYABLE"
    assert "Typed value verification failed" in result["error"]


@pytest.mark.asyncio
async def test_node_reason_skips_autogen_when_runtime_unavailable(mock_dependencies):
    engine = RightPupilEngine()
    await engine.start_session(headless=True)
    mock_dependencies["planner"].return_value.plan_next_step = AsyncMock(
        return_value=AUIIR(
            action_type="click",
            target=VisualLocator(strategy="visual", value="47"),
            params={},
        )
    )

    state = {
        "error": None,
        "use_existing_action": False,
        "action_intent": None,
        "task_description": "Click the Login button",
        "current_screenshot": "",
        "som_text": "ID 47: button Login",
        "history": [],
        "task_url": None,
    }

    with patch(
        "app.engines.right_pupil.get_autogen_runtime_status",
        return_value=SimpleNamespace(available=False, reason="legacy autogen incompatible"),
    ):
        result = await engine.node_reason(state)

    assert result["action_intent"].action_type == "click"
    mock_dependencies["planner"].return_value.plan_next_step.assert_awaited_once()
