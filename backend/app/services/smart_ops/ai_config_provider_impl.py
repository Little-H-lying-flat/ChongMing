"""
AI 配置提供者实现

基于 AIConfigService 实现 AIConfigProvider 协议，
供 AIClientManager 在应用级别注入使用。
"""

from typing import Dict

from app.core.ai_config_provider import AIConfigProvider
from app.core.ai_models import AIModule, ModelConfig
from app.services.smart_ops.ai_config_service import AIConfigService


class AIConfigProviderImpl(AIConfigProvider):
    """
    基于数据库的 AI 配置提供者

    委托给 AIConfigService，实现 Core 层定义的 AIConfigProvider 协议。
    """

    async def get_model_config(self, module: AIModule) -> ModelConfig:
        return await AIConfigService.get_model_config(module)

    async def log_cost(self, module: AIModule, model_id: str, usage: Dict[str, int]) -> None:
        await AIConfigService.log_cost(module, model_id, usage)
