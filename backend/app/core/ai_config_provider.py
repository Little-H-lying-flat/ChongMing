"""
AI 配置提供者协议 (Dependency Inversion)

定义 Core 层对 AI 配置的抽象需求。
Services 层负责提供具体实现，通过 DI 注入。

这避免了 Core -> Services 的直接依赖。
"""

from typing import Dict, Optional, Protocol, runtime_checkable

from app.core.ai_models import AIModule, ModelConfig


@runtime_checkable
class AIConfigProvider(Protocol):
    """AI 配置提供者协议"""

    async def get_model_config(self, module: AIModule) -> ModelConfig:
        """获取模块的模型配置"""
        ...

    async def log_cost(self, module: AIModule, model_id: str, usage: Dict[str, int]) -> None:
        """记录 AI 调用成本"""
        ...


class DefaultAIConfigProvider:
    """
    默认配置提供者 (Fallback)

    直接使用 ai_models 中的静态默认映射，不访问数据库。
    当没有注入具体实现时使用。
    """

    async def get_model_config(self, module: AIModule) -> ModelConfig:
        from app.core.ai_models import get_model_for_module
        return get_model_for_module(module)

    async def log_cost(self, module: AIModule, model_id: str, usage: Dict[str, int]) -> None:
        # 默认实现不记录成本
        pass
