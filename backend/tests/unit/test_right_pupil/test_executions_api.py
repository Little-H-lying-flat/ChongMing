import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.api.v1.endpoints.executions import router

# Setup app
app = FastAPI()
app.include_router(router, prefix="/executions")
client = TestClient(app)

def test_run_ui_task_endpoint():
    """Verify POST /executions/ui/run calls ExecutionService.run_ui_task"""
    with patch("app.api.v1.endpoints.executions.ExecutionService") as MockService:
        MockService.run_ui_task = AsyncMock(return_value=[{"step": 1, "status": "success"}])
        
        response = client.post(
            "/executions/ui/run",
            json={"prompt": "Search for AI", "url": "https://www.google.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "success"
        
        # Verify service was called correctly
        MockService.run_ui_task.assert_called_once_with("Search for AI", "https://www.google.com")
