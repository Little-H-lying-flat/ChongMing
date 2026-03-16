import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from app.core.ai_models import AIModule, DEFAULT_MODEL_MAPPING
from app.models.ai_config import AIModelConfig
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
