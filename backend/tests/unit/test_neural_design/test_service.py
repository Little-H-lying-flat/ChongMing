import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest

@pytest.fixture
def mock_ai():
    ai = AsyncMock()
    # Default mock response
    ai.simple_chat.return_value = '{"scenarios": [{"name": "Test Scenario", "description": "Desc", "test_points": ["Point1"]}]}'
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
    request = DesignRequest(
        project_id="p1", 
        requirement_text="Login feature"
    )
    
    # Setup mock for this test
    mock_ai.simple_chat.return_value = '{"scenarios": [{"name": "Test Scenario", "description": "Desc", "test_points": ["Point1"]}]}'
    
    scenarios = await service.analyze_requirement(request)
    
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Test Scenario"
    mock_ai.simple_chat.assert_called_once()

@pytest.mark.asyncio
async def test_generate_test_case(service, mock_ai, mock_retriever):
    # Mock AI response for test case generation
    mock_ai.simple_chat.return_value = '''
    {
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
    }
    '''
    
    scenario = {"name": "Login Scenario", "description": "User logs in", "test_points": ["Valid login"]}
    
    result = await service.generate_test_case(scenario, "p1")
    
    assert result.name == "Login" # From intent
    assert result.request.method == "POST"
    assert result.request.url == "/login"
    
    # Check if retriever was called
    mock_retriever.retrieve.assert_called_once()
    # Check if AI was called
    assert mock_ai.simple_chat.call_count == 1
