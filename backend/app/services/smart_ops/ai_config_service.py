
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from functools import lru_cache
from datetime import datetime
import time

from app.models.ai_config import AIModelConfig, AIProviderConfig, AICostLog
from app.core.ai_models import AIModule, ModelConfig, AVAILABLE_MODELS, DEFAULT_MODEL_MAPPING, ModelProvider
from app.core.database import async_session_maker
from loguru import logger

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
    CACHE_TTL = 300  # 5 minutes
    
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
        
        # Determine effective model_id from DB or Default
        model_id = DEFAULT_MODEL_MAPPING.get(module, "qwen-plus")
        override_config = None
        
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

        # Validate Model
        if model_id not in AVAILABLE_MODELS:
            logger.warning(f"Configured model {model_id} not found. Reverting to default.")
            model_id = "qwen-plus"
            
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
        return final_config

    @classmethod
    async def get_provider_config(cls, provider: ModelProvider) -> Optional[Dict[str, str]]:
        """
        Get API Key & Base URL for provider
        """
        # Cache check ...
        # Implementation omitted for brevity, assuming standard env vars as fallback
        return None 

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
        cls._last_cache_update = 0

    @classmethod
    async def get_all_module_configs(cls) -> List[Dict[str, Any]]:
        """
        获取所有模块的当前配置 (供 API 层使用)

        Returns:
            List of dicts with module, model_id, provider, temperature, max_tokens, is_custom
        """
        configs = []
        async with async_session_maker() as session:
            stmt = select(AIModelConfig)
            result = await session.execute(stmt)
            db_configs = {c.module: c for c in result.scalars().all()}

        for module in AIModule:
            default_model_id = DEFAULT_MODEL_MAPPING.get(module, "qwen-plus")
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
        async with async_session_maker() as session:
            stmt = select(AIProviderConfig).where(AIProviderConfig.provider == provider)
            result = await session.execute(stmt)
            db_conf = result.scalar_one_or_none()

            if db_conf:
                db_conf.api_key_ciphertext = api_key  # TODO: Encrypt
                db_conf.base_url = base_url
            else:
                db_conf = AIProviderConfig(
                    provider=provider,
                    api_key_ciphertext=api_key,  # TODO: Encrypt
                    base_url=base_url,
                )
                session.add(db_conf)

            await session.commit()
        return {"status": "success", "provider": provider}
