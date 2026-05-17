import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from app.core.ai_models import AIModule, DEFAULT_MODEL_MAPPING, ModelProvider
from app.models.ai_config import AIModelConfig, AIProviderConfig
from app.services.smart_ops import ai_config_service as ai_config_service_module
from app.services.smart_ops.ai_config_service import AIConfigService


@pytest.mark.asyncio
async def test_ensure_schema_ready_creates_and_seeds_defaults(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(ai_config_service_module, "async_session_maker", session_maker)
    AIConfigService.clear_cache()
    AIConfigService._schema_ready = False
    AIConfigService._schema_lock = None

    await AIConfigService.ensure_schema_ready()

    async with session_maker() as session:
        result = await session.execute(select(AIModelConfig))
        records = result.scalars().all()

    modules = {record.module for record in records}
    assert len(records) >= len(DEFAULT_MODEL_MAPPING)
    assert AIModule.AGENT_RIGHT_VISUAL.value in modules
    assert AIModule.AGENT_NEURAL_ADMIN.value in modules

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_model_config_updates_cache_timestamp(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(ai_config_service_module, "async_session_maker", session_maker)
    AIConfigService.clear_cache()
    AIConfigService._schema_ready = False
    AIConfigService._schema_lock = None

    config = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_VISUAL)

    assert config.model_id == DEFAULT_MODEL_MAPPING[AIModule.AGENT_RIGHT_VISUAL]
    assert AIConfigService._last_cache_update > 0
    assert AIConfigService._config_cache[AIModule.AGENT_RIGHT_VISUAL.value].model_id == config.model_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_update_provider_config_encrypts_and_reads_from_db(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(ai_config_service_module, "async_session_maker", session_maker)
    monkeypatch.setattr("app.core.config.settings.ENCRYPTION_KEY", "test_encryption_key_32bytes")
    AIConfigService.clear_cache()
    AIConfigService._schema_ready = False
    AIConfigService._schema_lock = None

    api_key = "sk-provider-secret"
    base_url = "https://dashscope.example/v1"
    result = await AIConfigService.update_provider_config_db("dashscope", api_key, base_url)

    assert result == {"status": "success", "provider": "dashscope"}

    async with session_maker() as session:
        db_result = await session.execute(
            select(AIProviderConfig).where(AIProviderConfig.provider == "dashscope")
        )
        record = db_result.scalar_one()

    assert record.api_key_ciphertext != api_key
    assert record.base_url == base_url

    config = await AIConfigService.get_provider_config(ModelProvider.DASHSCOPE)
    assert config == {"api_key": api_key, "base_url": base_url}

    await engine.dispose()


@pytest.mark.asyncio
async def test_update_provider_config_rejects_unknown_provider(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(ai_config_service_module, "async_session_maker", session_maker)
    AIConfigService.clear_cache()
    AIConfigService._schema_ready = False
    AIConfigService._schema_lock = None

    with pytest.raises(ValueError, match="Unsupported provider"):
        await AIConfigService.update_provider_config_db("anthropic", "sk-secret")

    await engine.dispose()
