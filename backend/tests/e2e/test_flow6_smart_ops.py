import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import patch, MagicMock

from app.models.base import Base
from app.models.ai_config import AIModelConfig
from app.services.smart_ops.ai_config_service import AIConfigService
from app.core.ai_models import AIModule, AVAILABLE_MODELS

# --- In-Memory DB Setup ---
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def test_db_session():
    """
    Create an isolated in-memory DB for testing.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    
    # Create Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create Session Factory
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with session_factory() as session:
        yield session
        # Cleanup (Optional for memory DB, but good practice)
        await session.rollback()
        
    await engine.dispose()

@pytest.fixture(autouse=True)
def mock_session_maker(test_db_session):
    """
    Patch the async_session_maker in the service to use our test session.
    Since the service uses `async with async_session_maker() as session:`,
    we need to mock the context manager return.
    """
    # We need a context manager mock that yields the test_db_session
    class MockSessionContext:
        def __init__(self, session):
            self.session = session
        
        async def __aenter__(self):
            return self.session
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # The service calls async_session_maker() which returns the context manager
    mock_maker = MagicMock(return_value=MockSessionContext(test_db_session))
    
    with patch("app.services.smart_ops.ai_config_service.async_session_maker", mock_maker):
        yield

@pytest.mark.asyncio
async def test_flow6_happy_path_config_update(test_db_session):
    """
    Flow 6 Scenario A: Config Update & Cache Invalidation
    1. Get Default Config (Cache Miss -> DB Miss -> Default)
    2. Update Config (Write DB -> Clear Cache)
    3. Get New Config (Cache Miss -> DB Hit -> New Config)
    """
    module = AIModule.GENERAL_CHAT
    default_model_id = "qwen-flash" # From DEFAULT_MODEL_MAPPING
    new_model_id = "qwen-max"
    
    # 0. Ensure Cache is empty initially
    AIConfigService.clear_cache()
    
    # 1. Verify Default State
    config_default = await AIConfigService.get_model_config(module)
    assert config_default.model_id == default_model_id
    assert config_default.max_tokens == 8192 # Default for qwen-flash
    
    # Verify it's cached now
    assert module.value in AIConfigService._config_cache
    
    # 2. Update Config
    # Change model to qwen-max and max_tokens to 100
    updated_info = await AIConfigService.update_module_config_db(
        module=module.value,
        model_id=new_model_id,
        max_tokens=100
    )
    
    assert updated_info["model_id"] == new_model_id
    assert updated_info["max_tokens"] == 100
    
    # Verify Cache is cleared (Service calls clear_cache)
    assert len(AIConfigService._config_cache) == 0
    
    # 3. Verify New Config Retrieval
    config_new = await AIConfigService.get_model_config(module)
    
    assert config_new.model_id == new_model_id
    assert config_new.max_tokens == 100 # Should use override
    assert config_new.provider == AVAILABLE_MODELS[new_model_id].provider
    
    # Verify DB Persistence directly
    # (Just to be triple sure the service actually wrote to DB)
    from sqlalchemy.future import select
    stmt = select(AIModelConfig).where(AIModelConfig.module == module.value)
    result = await test_db_session.execute(stmt)
    db_record = result.scalar_one()
    
    assert db_record.model_id == new_model_id
    assert db_record.max_tokens == 100

@pytest.mark.asyncio
async def test_flow6_provider_api_key_update(test_db_session):
    """
    Flow 6 Helper: Test Provider Config Update
    """
    provider = "dashscope"
    new_api_key = "sk-new-secret-key"
    
    # Update API Key
    await AIConfigService.update_provider_config_db(
        provider=provider,
        api_key=new_api_key
    )
    
    # Verify DB
    from sqlalchemy.future import select
    from app.models.ai_config import AIProviderConfig
    
    stmt = select(AIProviderConfig).where(AIProviderConfig.provider == provider)
    result = await test_db_session.execute(stmt)
    record = result.scalar_one()
    
    assert record.api_key_ciphertext == new_api_key
