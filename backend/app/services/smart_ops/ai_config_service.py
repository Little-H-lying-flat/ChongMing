
import asyncio
import base64
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from sqlalchemy.future import select
import time

from app.models.ai_config import AIModelConfig, AIProviderConfig, AICostLog
from app.core.ai_models import AIModule, ModelConfig, AVAILABLE_MODELS, DEFAULT_MODEL_MAPPING, ModelProvider, get_default_model_id
from app.core.database import async_session_maker
from app.models.base import Base
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

class AIConfigService:
    """
    AI 配置服务 (AI Config Service)
    
    负责:
    1. 获取模块的模型配置 (优先查库，缓存优化)
    2. 获取提供商的 API Key (解密)
    3. 记录成本日志
    4. 动态更新配置
    """
    
    _config_cache: Dict[str, ModelConfig] = {}
    _provider_cache: Dict[str, Dict[str, str]] = {}
    _last_cache_update: float = 0
    _schema_ready: bool = False
    _schema_lock: Optional[asyncio.Lock] = None
    _schema_warning: Optional[str] = None
    CACHE_TTL = 300  # 5 minutes

    @classmethod
    def _init_fernet(cls) -> Fernet | None:
        from app.core.config import settings

        key = getattr(settings, "ENCRYPTION_KEY", None)
        if not key:
            return None
        if len(key) < 32:
            key = key.ljust(32, "0")
        key_bytes = base64.urlsafe_b64encode(key[:32].encode())
        return Fernet(key_bytes)

    @classmethod
    def _encrypt_secret(cls, value: str) -> str:
        fernet = cls._init_fernet()
        if not fernet:
            return value
        return fernet.encrypt(value.encode()).decode()

    @classmethod
    def _decrypt_secret(cls, value: str) -> str:
        fernet = cls._init_fernet()
        if not fernet:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    @classmethod
    async def ensure_schema_ready(cls) -> None:
        """Ensure AI config tables exist and seed default module mappings once."""
        if cls._schema_ready:
            return

        if cls._schema_lock is None:
            cls._schema_lock = asyncio.Lock()

        async with cls._schema_lock:
            if cls._schema_ready:
                return

            bind = getattr(async_session_maker, "kw", {}).get("bind")
            if bind is None:
                cls._schema_warning = "async_session_maker is not bound to an engine"
                logger.warning(
                    "AI config schema bootstrap skipped; continuing with code defaults: "
                    f"{cls._schema_warning}"
                )
                cls._schema_ready = True
                return

            try:
                async with bind.begin() as conn:
                    await conn.run_sync(
                        lambda sync_conn: Base.metadata.create_all(
                            sync_conn,
                            tables=[
                                AIModelConfig.__table__,
                                AIProviderConfig.__table__,
                                AICostLog.__table__,
                            ],
                        )
                    )

                async with async_session_maker() as session:
                    stmt = select(AIModelConfig.module)
                    result = await session.execute(stmt)
                    existing_modules = set(result.scalars().all())

                    new_rows = []
                    for module in AIModule:
                        if module.value in existing_modules:
                            continue
                        model_id = get_default_model_id(module)
                        if not model_id or model_id not in AVAILABLE_MODELS:
                            continue

                        model_config = AVAILABLE_MODELS[model_id]
                        new_rows.append(
                            AIModelConfig(
                                module=module.value,
                                model_id=model_config.model_id,
                                provider=model_config.provider.value,
                                temperature=model_config.temperature,
                                max_tokens=model_config.max_tokens,
                            )
                        )

                    if new_rows:
                        session.add_all(new_rows)
                        await session.commit()
            except SQLAlchemyError as exc:
                cls._schema_warning = str(exc)
                logger.warning(
                    "AI config schema bootstrap degraded; continuing with code defaults: "
                    f"{exc}"
                )
            finally:
                cls._schema_ready = True
    
    @classmethod
    async def get_model_config(cls, module: AIModule, session: Optional[Session] = None) -> ModelConfig:
        """
        获取模块的模型配置
        
        Logic: Cache -> DB -> Default
        """
        # Check Cache
        if time.time() - cls._last_cache_update < cls.CACHE_TTL:
            if module.value in cls._config_cache:
                return cls._config_cache[module.value]
        
        default_model_id = get_default_model_id(module)
        model_id = default_model_id
        override_config = None
        
        try:
            await cls.ensure_schema_ready()
            if session:
                stmt = select(AIModelConfig).where(AIModelConfig.module == module.value)
                result = await session.execute(stmt)
                db_config = result.scalar_one_or_none()

                if db_config:
                    model_id = db_config.model_id
                    override_config = db_config
            else:
                # Create a localized session if none provided?
                # Ideally calling context should provide session.
                # For brevity/safety in async context, we might skip DB if no session or use async_session_maker
                async with async_session_maker() as local_session:
                    stmt = select(AIModelConfig).where(AIModelConfig.module == module.value)
                    result = await local_session.execute(stmt)
                    db_config = result.scalar_one_or_none()
                    if db_config:
                        model_id = db_config.model_id
                        override_config = db_config
        except SQLAlchemyError as exc:
            logger.warning(
                f"AI model config table/query unavailable, fallback to defaults for module={module.value}: {exc}"
            )

        if model_id not in AVAILABLE_MODELS:
            logger.warning(
                f"Configured model {model_id} not found for module={module.value}; "
                f"reverting to default {default_model_id}."
            )
            model_id = default_model_id
            override_config = None

        if model_id not in AVAILABLE_MODELS:
            raise ValueError(f"Default model {model_id} is not registered for module={module.value}")

        base_config = AVAILABLE_MODELS[model_id]
        
        # Apply Overrides (Temperature, MaxTokens)
        if override_config:
            # We create a new copy to avoid mutating global state
            final_config = ModelConfig(
                model_id=base_config.model_id,
                provider=base_config.provider,
                capability=base_config.capability,
                max_tokens=override_config.max_tokens or base_config.max_tokens,
                temperature=override_config.temperature if override_config.temperature is not None else base_config.temperature,
                description=base_config.description,
                cost_per_1k_tokens=base_config.cost_per_1k_tokens,
                system_prompt=override_config.system_prompt
            )
        else:
            final_config = base_config
            
        # Update Cache
        cls._config_cache[module.value] = final_config
        cls._last_cache_update = time.time()
        return final_config

    @classmethod
    async def get_provider_config(cls, provider: ModelProvider) -> Optional[Dict[str, str]]:
        """
        Get API Key & Base URL for provider
        """
        from app.core.config import settings

        cache_key = provider.value
        cached = cls._provider_cache.get(cache_key)
        if cached and time.time() - cls._last_cache_update < cls.CACHE_TTL:
            return cached

        provider_configs = {
            ModelProvider.DASHSCOPE: {
                "api_key": settings.QWEN_API_KEY,
                "base_url": settings.QWEN_BASE_URL,
            },
            ModelProvider.OPENAI: {
                "api_key": settings.OPENAI_API_KEY,
                "base_url": settings.OPENAI_BASE_URL,
            },
            ModelProvider.GEMINI: {
                "api_key": settings.GEMINI_API_KEY,
                "base_url": settings.GEMINI_BASE_URL,
            },
        }
        fallback_config = provider_configs.get(provider)

        try:
            await cls.ensure_schema_ready()
            async with async_session_maker() as session:
                stmt = select(AIProviderConfig).where(
                    AIProviderConfig.provider == provider.value,
                    AIProviderConfig.is_active == True,
                )
                result = await session.execute(stmt)
                db_config = result.scalar_one_or_none()
                if db_config and db_config.api_key_ciphertext:
                    config = {
                        "api_key": cls._decrypt_secret(db_config.api_key_ciphertext),
                        "base_url": db_config.base_url or (fallback_config or {}).get("base_url", ""),
                    }
                    cls._provider_cache[cache_key] = config
                    cls._last_cache_update = time.time()
                    return config
        except SQLAlchemyError as exc:
            logger.warning(f"AI provider config unavailable for provider={provider.value}: {exc}")

        if not fallback_config or not fallback_config["api_key"]:
            return None
        cls._provider_cache[cache_key] = fallback_config
        cls._last_cache_update = time.time()
        return fallback_config

    @classmethod
    async def log_cost(cls, module: AIModule, model_id: str, usage: Dict[str, int]):
        """
        异步记录成本
        """
        if not usage:
            return
            
        try:
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total = usage.get("total_tokens", 0)
            
            # Calculate cost
            config = AVAILABLE_MODELS.get(model_id)
            cost = 0.0
            if config:
                cost = (total / 1000.0) * config.cost_per_1k_tokens
            
            await cls.ensure_schema_ready()
            async with async_session_maker() as session:
                log_entry = AICostLog(
                    module=module.value,
                    model_id=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_cost=cost
                )
                session.add(log_entry)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to log AI cost: {e}")

    @classmethod
    def clear_cache(cls):
        cls._config_cache.clear()
        cls._provider_cache.clear()
        cls._last_cache_update = 0

    @classmethod
    async def get_all_module_configs(cls) -> List[Dict[str, Any]]:
        """
        获取所有模块的当前配置 (供 API 层使用)

        Returns:
            List of dicts with module, model_id, provider, temperature, max_tokens, is_custom
        """
        configs = []
        await cls.ensure_schema_ready()
        db_configs = {}
        try:
            async with async_session_maker() as session:
                stmt = select(AIModelConfig)
                result = await session.execute(stmt)
                db_configs = {c.module: c for c in result.scalars().all()}
        except SQLAlchemyError as exc:
            logger.warning(
                f"AI config listing unavailable; returning code defaults only: {exc}"
            )

        for module in AIModule:
            default_model_id = get_default_model_id(module)
            default_config = AVAILABLE_MODELS.get(default_model_id)

            db_conf = db_configs.get(module.value)
            if db_conf:
                configs.append({
                    "module": module.value,
                    "model_id": db_conf.model_id,
                    "provider": db_conf.provider,
                    "temperature": db_conf.temperature,
                    "max_tokens": db_conf.max_tokens,
                    "is_custom": True,
                })
            elif default_config:
                configs.append({
                    "module": module.value,
                    "model_id": default_config.model_id,
                    "provider": default_config.provider.value,
                    "temperature": default_config.temperature,
                    "max_tokens": default_config.max_tokens,
                    "is_custom": False,
                })
        return configs

    @classmethod
    async def update_module_config_db(
        cls,
        module: str,
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        更新模块配置 (供 API 层使用)

        Returns:
            Dict representing the updated config
        Raises:
            ValueError if model_id is unknown
        """
        if model_id not in AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {model_id}")

        target_model = AVAILABLE_MODELS[model_id]

        await cls.ensure_schema_ready()
        async with async_session_maker() as session:
            stmt = select(AIModelConfig).where(AIModelConfig.module == module)
            result = await session.execute(stmt)
            db_config = result.scalar_one_or_none()

            if db_config:
                db_config.model_id = model_id
                db_config.provider = target_model.provider.value
                db_config.temperature = temperature
                db_config.max_tokens = max_tokens
            else:
                db_config = AIModelConfig(
                    module=module,
                    model_id=model_id,
                    provider=target_model.provider.value,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                session.add(db_config)

            await session.commit()
            await session.refresh(db_config)

            cls.clear_cache()

            return {
                "module": db_config.module,
                "model_id": db_config.model_id,
                "provider": db_config.provider,
                "temperature": db_config.temperature,
                "max_tokens": db_config.max_tokens,
                "is_custom": True,
            }

    @classmethod
    async def update_provider_config_db(
        cls,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        更新提供商配置 (供 API 层使用)
        """
        if not api_key.strip():
            raise ValueError("API key must not be empty")

        provider_value = provider.strip().lower()
        allowed_providers = {item.value for item in ModelProvider if item != ModelProvider.LOCAL}
        if provider_value not in allowed_providers:
            raise ValueError(f"Unsupported provider: {provider}")

        encrypted_key = cls._encrypt_secret(api_key)

        await cls.ensure_schema_ready()
        async with async_session_maker() as session:
            stmt = select(AIProviderConfig).where(AIProviderConfig.provider == provider_value)
            result = await session.execute(stmt)
            db_conf = result.scalar_one_or_none()

            if db_conf:
                db_conf.api_key_ciphertext = encrypted_key
                db_conf.base_url = base_url
                db_conf.is_active = True
            else:
                db_conf = AIProviderConfig(
                    provider=provider_value,
                    api_key_ciphertext=encrypted_key,
                    base_url=base_url,
                    is_active=True,
                )
                session.add(db_conf)

            await session.commit()

        cls.clear_cache()
        return {"status": "success", "provider": provider_value}

    @classmethod
    async def get_token_metrics(cls, days: int = 7) -> List[Dict[str, Any]]:
        """
        获取过去 N 天的模型 Token 消耗和估算成本统计
        """
        from datetime import timedelta, datetime, timezone
        from collections import defaultdict
        
        # Determine cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        async with async_session_maker() as session:
            stmt = select(AICostLog).where(AICostLog.created_at >= cutoff_date)
            result = await session.execute(stmt)
            logs = result.scalars().all()
            
        # Group by Date (YYYY-MM-DD) and accumulate tokens per model and total cost
        daily_metrics = defaultdict(lambda: {"cost": 0.0})
        
        for log in logs:
            if not log.created_at:
                continue
            date_str = log.created_at.strftime("%Y-%m-%d")
            model_key = log.model_id
            
            entry = daily_metrics[date_str]
            entry["date"] = date_str
            
            if model_key not in entry:
                entry[model_key] = 0
                
            total_tokens = (log.input_tokens or 0) + (log.output_tokens or 0)
            entry[model_key] += total_tokens
            entry["cost"] += (log.total_cost or 0.0)
            
        # Round cost for cleaner frontend display
        for entry in daily_metrics.values():
            entry["cost"] = round(entry["cost"], 4)
            
        # Return chronologically sorted array
        return sorted(list(daily_metrics.values()), key=lambda x: x.get("date", ""))
