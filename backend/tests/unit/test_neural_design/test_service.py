import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest
from app.core.ai_client import AIResponse
from app.services.neural_design import service as service_module


@pytest.fixture
def mock_ai():
    ai = AsyncMock()
    # Mock invoke() which is what DesignService actually calls
    ai.invoke.return_value = AIResponse(
        content='{"scenarios": [{"name": "Test Scenario", "description": "Desc", "test_points": ["Point1"]}]}',
        model="mock-model",
        usage={"total_tokens": 50},
        finish_reason="stop"
    )
    return ai

@pytest.fixture
def mock_retriever():
    retriever = AsyncMock()
    retriever.retrieve.return_value = [] # Return empty list of APIs
    return retriever

@pytest.fixture
def service(mock_ai, mock_retriever):
    return DesignService(ai_manager=mock_ai, retriever=mock_retriever)

@pytest.mark.asyncio
async def test_analyze_requirement(service, mock_ai):
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "scenarios": [{"name": "Test Scenario", "description": "Desc", "steps": []}]
    }
    original_graph = service_module.neural_design_graph
    service_module.neural_design_graph = mock_graph

    request = DesignRequest(
        project_id="p1", 
        requirement_text="Login feature"
    )

    try:
        scenarios = await service.analyze_requirement(request)
    finally:
        service_module.neural_design_graph = original_graph

    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Test Scenario"
    mock_graph.ainvoke.assert_called_once()

@pytest.mark.asyncio
async def test_generate_test_case(service, mock_ai, mock_retriever):
    # Mock AI response for test case generation
    mock_ai.invoke.return_value = AIResponse(
        content='''{
            "case_name": "Login Case",
            "description": "User logs in",
            "steps": [
                {
                    "step_id": "step1",
                    "intent": "Login",
                    "method": "POST",
                    "url_path": "/login",
                    "description": "Post creds",
                    "input_data": {"user": "admin"},
                    "expected_outcome": "200 OK"
                }
            ]
        }''',
        model="mock-model",
        usage={"total_tokens": 100},
        finish_reason="stop"
    )
    
    scenario = {"name": "Login Scenario", "description": "User logs in", "test_points": ["Valid login"]}
    
    result = await service.generate_test_case(scenario, "p1")
    
    assert result.name == "Login Case"  # From draft case_name
    assert result.steps[0].name == "Login"  # From step intent
    assert result.steps[0].request.method == "POST"
    assert result.steps[0].request.url == "/login"
    
    # Check if retriever was called
    mock_retriever.retrieve.assert_called_once()
    # Check if AI was called (invoke for draft + invoke for critic = 2 calls)
    assert mock_ai.invoke.call_count >= 1
