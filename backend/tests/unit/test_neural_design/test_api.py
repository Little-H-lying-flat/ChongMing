import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.api.v1.endpoints.design import router, get_design_service
from app.services.neural_design.service import DesignService
from app.services.neural_design.models import RefinedTCIR, RefinedRequestSpec

# Setup standalone app for testing
app = FastAPI()
app.include_router(router, prefix="/design")
client = TestClient(app)

@pytest.fixture
def mock_service():
    service = AsyncMock(spec=DesignService)
    return service

def test_analyze_endpoint(mock_service):
    # Override dependency
    app.dependency_overrides[get_design_service] = lambda: mock_service
    
    mock_service.analyze_requirement.return_value = [{"name": "Scenario 1"}]
    
    response = client.post(
        "/design/analyze",
        json={"project_id": "p1", "requirement_text": "Login"}
    )
    
    assert response.status_code == 200
    assert response.json() == [{"name": "Scenario 1"}]
    mock_service.analyze_requirement.assert_called_once()
    
    # Cleanup
    app.dependency_overrides.clear()

def test_generate_endpoint(mock_service):
    app.dependency_overrides[get_design_service] = lambda: mock_service
    
    # Mock return value
    # Needs to match RefinedTCIR Pydantic model structure
    mock_tcir = RefinedTCIR(
        id="tc1",
        name="Login Test",
        request=RefinedRequestSpec(method="POST", url="/login")
    )
    mock_service.generate_test_case.return_value = mock_tcir
    
    response = client.post(
        "/design/generate",
        json={
            "scenario": {"name": "Login", "description": "test"},
            "project_id": "p1"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "tc1"
    assert data["name"] == "Login Test"
    
    # Cleanup
    app.dependency_overrides.clear()

def test_error_handling(mock_service):
    app.dependency_overrides[get_design_service] = lambda: mock_service
    
    mock_service.analyze_requirement.side_effect = Exception("LLM Error")
    
    response = client.post(
        "/design/analyze",
        json={"project_id": "p1", "requirement_text": "Fail"}
    )
    
    assert response.status_code == 500
    assert "LLM Error" in response.json()["detail"]
