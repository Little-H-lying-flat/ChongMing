
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.ai_client import AIClientManager, init_ai_manager
from app.core.ai_models import AIModule, ModelConfig, ModelProvider, ModelCapability
from app.core.ai_client import Message, AIResponse
from app.core.ai_config_provider import AIConfigProvider

# Mock Config Provider
class MockAIConfigProvider(AIConfigProvider):
    async def get_model_config(self, module: AIModule) -> ModelConfig:
        return ModelConfig(
            model_id="qwen-turbo",
            provider=ModelProvider.DASHSCOPE,
            capability=ModelCapability.TEXT,
            max_tokens=100,
            temperature=0.7,
        )
    
    async def log_cost(self, module: AIModule, model_id: str, usage: dict) -> None:
        pass

@pytest.fixture
def mock_config_provider():
    return MockAIConfigProvider()

@pytest.fixture
def ai_client(mock_config_provider):
    # Reset singleton
    import app.core.ai_client
    app.core.ai_client._ai_manager = None
    return init_ai_manager(config_provider=mock_config_provider)

@pytest.mark.asyncio
async def test_ai_client_invoke(ai_client):
    """Test standard invoke with mocked provider"""
    
    # Mock the internal DashScope client
    with patch("app.core.ai_client.DashScopeClient") as MockDashScope:
        mock_ds = MockDashScope.return_value
        mock_ds.chat = AsyncMock(return_value=AIResponse(
            content="Hello World",
            model="qwen-turbo",
            usage={"total_tokens": 10},
            finish_reason="stop"
        ))
        
        # Inject mock client into manager (since _init_clients happens in __init__)
        # We need to ensure _get_client returns our mock
        from app.core.ai_models import ModelProvider
        ai_client._clients[ModelProvider.DASHSCOPE] = mock_ds

        messages = [Message(role="user", content="Hi")]
        response = await ai_client.invoke(AIModule.GENERAL_CHAT, messages)
        
        assert response.content == "Hello World"
        assert response.model == "qwen-turbo"
        
        # Verify provider.get_model_config was called (implicitly by success)
        # Verify internal client.chat was called
        mock_ds.chat.assert_called_once()


@pytest.mark.asyncio
async def test_ai_client_invoke_override(ai_client):
    """Test invoke with model override"""
    with patch("app.core.ai_client.DashScopeClient") as MockDashScope:
        mock_ds = MockDashScope.return_value
        mock_ds.chat = AsyncMock(return_value=AIResponse(
            content="Overridden",
            model="qwen-plus", 
            usage={"total_tokens": 10},
            finish_reason="stop"
        ))
        from app.core.ai_models import ModelProvider
        ai_client._clients[ModelProvider.DASHSCOPE] = mock_ds
        
        # "qwen-plus" must be in AVAILABLE_MODELS for override to work
        # We assume it is.
        
        messages = [Message(role="user", content="Hi")]
        # Override with qwen-plus
        response = await ai_client.invoke(
            AIModule.GENERAL_CHAT, 
            messages, 
            model_override="qwen-plus"
        )
        
        assert response.content == "Overridden"

