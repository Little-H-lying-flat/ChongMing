
import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.core.ai_models import AIModule
from app.services.smart_ops.ai_config_service import AIConfigService

# Mock Auth Header (if needed)
# settings.FIRST_SUPERUSER = "admin"
# settings.FIRST_SUPERUSER_PASSWORD = "admin"

@pytest.mark.asyncio
async def test_list_models(async_client: AsyncClient):
    """Ref: GET /api/v1/smart-ops/models"""
    response = await async_client.get("/api/v1/smart-ops/models")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Verify structure
    first = data[0]
    assert "model_id" in first
    assert "provider" in first
    assert "cost_per_1k_tokens" in first

@pytest.mark.asyncio
async def test_get_config(async_client: AsyncClient):
    """Ref: GET /api/v1/smart-ops/config"""
    response = await async_client.get("/api/v1/smart-ops/config")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # Check default config presence
    found_chat = False
    for item in data:
        if item["module"] == AIModule.GENERAL_CHAT.value:
            found_chat = True
            break
    assert found_chat

@pytest.mark.asyncio
async def test_update_config(async_client: AsyncClient):
    """Ref: POST /api/v1/smart-ops/config"""
    
    module = AIModule.GENERAL_CHAT.value
    new_model = "qwen-max"
    
    payload = {
        "module": module,
        "model_id": new_model,
        "temperature": 0.5,
        "max_tokens": 2048
    }
    
    # 1. Update
    response = await async_client.post("/api/v1/smart-ops/config", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["module"] == module
    assert data["model_id"] == new_model
    assert data["temperature"] == 0.5
    assert data["is_custom"] is True
    
    # 2. Verify Get
    response = await async_client.get("/api/v1/smart-ops/config")
    data = response.json()
    
    overridden = next((x for x in data if x["module"] == module), None)
    assert overridden
    assert overridden["model_id"] == new_model
    assert overridden["temperature"] == 0.5

@pytest.mark.asyncio
async def test_invalid_model_update(async_client: AsyncClient):
    """Ref: POST /api/v1/smart-ops/config with invalid model"""
    payload = {
        "module": AIModule.GENERAL_CHAT.value,
        "model_id": "invalid-model-id-999"
    }
    response = await async_client.post("/api/v1/smart-ops/config", json=payload)
    assert response.status_code == 400
