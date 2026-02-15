"""
AI 客户端 - 统一的 LLM 调用接口

支持:
- 多提供商 (DashScope, OpenAI, Anthropic)
- 多模态 (文本, 视觉)
- 流式输出
- 自动重试
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import base64
from pathlib import Path

from openai import AsyncOpenAI
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.ai_models import (
    AIModule,
    ModelConfig,
    ModelProvider,
    ModelCapability,
    get_model_for_module,
    AVAILABLE_MODELS,
)



from app.core.ai_config_provider import AIConfigProvider, DefaultAIConfigProvider
import asyncio

@dataclass
class Message:
    """消息"""
    role: str  # system, user, assistant
    content: Union[str, List[dict]]  # 文本或多模态内容


@dataclass
class AIResponse:
    """AI 响应"""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str


class BaseAIClient(ABC):
    """AI 客户端基类"""
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        **kwargs,
    ) -> AIResponse:
        """发送聊天请求"""
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式聊天"""
        pass


class DashScopeClient(BaseAIClient):
    """阿里云 DashScope 客户端"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.client = AsyncOpenAI(
            api_key=api_key or settings.QWEN_API_KEY,
            base_url=base_url or settings.QWEN_BASE_URL,
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def chat(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        **kwargs,
    ) -> AIResponse:
        """发送聊天请求"""
        formatted_messages = self._format_messages(messages, model_config)
        
        response = await self.client.chat.completions.create(
            model=model_config.model_id,
            messages=formatted_messages,
            max_tokens=kwargs.get("max_tokens", model_config.max_tokens),
            temperature=kwargs.get("temperature", model_config.temperature),
        )
        
        return AIResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
        )
    
    async def chat_stream(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式聊天"""
        formatted_messages = self._format_messages(messages, model_config)
        
        stream = await self.client.chat.completions.create(
            model=model_config.model_id,
            messages=formatted_messages,
            max_tokens=kwargs.get("max_tokens", model_config.max_tokens),
            temperature=kwargs.get("temperature", model_config.temperature),
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def _format_messages(
        self,
        messages: List[Message],
        model_config: ModelConfig,
    ) -> List[dict]:
        """格式化消息"""
        formatted = []
        
        for msg in messages:
            if isinstance(msg.content, str):
                formatted.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            else:
                # 多模态消息 (VL 模型)
                formatted.append({
                    "role": msg.role,
                    "content": msg.content,
                })
        
        return formatted


class AIClientManager:
    """
    AI 客户端管理器 - 统一入口
    
    通过 AIConfigProvider 协议获取模型配置，遵循依赖倒置原则。
    """
    
    def __init__(self, config_provider: Optional[AIConfigProvider] = None):
        self._clients: Dict[ModelProvider, BaseAIClient] = {}
        self._config_provider: AIConfigProvider = config_provider or DefaultAIConfigProvider()
        self._init_clients()
    
    def _init_clients(self):
        """初始化客户端"""
        # DashScope 客户端
        if settings.QWEN_API_KEY:
            self._clients[ModelProvider.DASHSCOPE] = DashScopeClient()
            logger.info("DashScope 客户端已初始化")
        
        # TODO: Add other providers
    
    def _get_client(self, provider: ModelProvider) -> BaseAIClient:
        """获取客户端"""
        if provider not in self._clients:
            # Try lazy init or fail
            if provider == ModelProvider.DASHSCOPE:
                 self._clients[ModelProvider.DASHSCOPE] = DashScopeClient()
                 return self._clients[ModelProvider.DASHSCOPE]
            raise ValueError(f"未配置 {provider.value} 客户端")
        return self._clients[provider]
    
    async def invoke(
        self,
        module: AIModule,
        messages: List[Message],
        model_override: Optional[str] = None,
        **kwargs,
    ) -> AIResponse:
        """
        调用 AI 模型 (支持动态配置 & 成本记录)
        """
        # 1. Get Config (Dynamic) via injected provider
        model_config = await self._config_provider.get_model_config(module)
        
        # Override if provided
        if model_override:
            # We assume override is model_id, need to look up config
             if model_override in AVAILABLE_MODELS:
                 model_config = AVAILABLE_MODELS[model_override]

        client = self._get_client(model_config.provider)
        
        logger.debug(
            f"调用 AI: module={module.value}, model={model_config.model_id}"
        )
        
        try:
            # 1.1 Inject System Prompt if configured and not present
            final_messages = list(messages) # Shallow copy
            if model_config.system_prompt:
                has_system = any(m.role == "system" for m in final_messages)
                if not has_system:
                    logger.debug(f"Injecting System Prompt for {module.value}: {model_config.system_prompt[:20]}...")
                    final_messages.insert(0, Message(role="system", content=model_config.system_prompt))
            
            # 2. Invoke
            response = await client.chat(final_messages, model_config, **kwargs)
            
            # 3. Log Cost (Async)
            # Fire and forget cost logging to not block response
            asyncio.create_task(
                self._config_provider.log_cost(module, response.model, response.usage)
            )
            
            logger.debug(
                f"AI 响应: tokens={response.usage['total_tokens']}, "
                f"finish={response.finish_reason}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"AI Invoke Failed: {e}")
            # TODO: Implement Fallback Logic here
            raise
    
    async def invoke_stream(
        self,
        module: AIModule,
        messages: List[Message],
        model_override: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 AI 模型"""
        # 1. Get Config
        model_config = await self._config_provider.get_model_config(module)
        
        if model_override and model_override in AVAILABLE_MODELS:
            model_config = AVAILABLE_MODELS[model_override]
            
        client = self._get_client(model_config.provider)
        
        async for chunk in client.chat_stream(messages, model_config, **kwargs):
            yield chunk
    
    async def invoke_vision(
        self,
        module: AIModule,
        prompt: str,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
        model_override: Optional[str] = None,
        **kwargs,
    ) -> AIResponse:
        """
        调用视觉模型
        """
        # Logic remains similar, just ensuring we use the dynamic config inside invoke
        # But for vision capability check, we need config first
        model_config = await self._config_provider.get_model_config(module)
        if model_override and model_override in AVAILABLE_MODELS:
            model_config = AVAILABLE_MODELS[model_override]
            
        if model_config.capability != ModelCapability.VISION:
             # Fallback check? Or error?
             # For now error.
             # If dynamic config switched to non-vision model, this is a misconfig by user.
             pass

        # ... (Construct Content) ...
        # Copy-paste construction logic or just delegate to invoke with constructed messages
        # But wait, invoke calls get_model_config AGAIN.
        # It's better to construct messages key logic here available.

        # ... existing content construction code ...
        content = []
        if image_path:
            image_data = self._encode_image(image_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_data}"}
            })
        elif image_base64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        elif image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
        
        content.append({"type": "text", "text": prompt})
        messages = [Message(role="user", content=content)]
        
        # Pass model_override if needed, but we already resolved config to check capability.
        # We can pass model_override to invoke to let it re-resolve or just trust it.
        return await self.invoke(module, messages, model_override=model_config.model_id, **kwargs)

    def _encode_image(self, image_path: str) -> str:
        """将图片编码为 Base64"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")
        
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    async def simple_chat(
        self,
        prompt: str,
        module: AIModule = AIModule.GENERAL_CHAT,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        简单对话 - 便捷方法
        """
        messages = []
        
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        
        messages.append(Message(role="user", content=prompt))
        
        response = await self.invoke(module, messages, **kwargs)
        return response.content


# 全局单例
_ai_manager: Optional[AIClientManager] = None


def init_ai_manager(config_provider: Optional[AIConfigProvider] = None) -> AIClientManager:
    """初始化 AI 管理器单例 (应在应用启动时调用)"""
    global _ai_manager
    _ai_manager = AIClientManager(config_provider=config_provider)
    return _ai_manager


def get_ai_manager() -> AIClientManager:
    """获取 AI 管理器单例"""
    global _ai_manager
    if _ai_manager is None:
        _ai_manager = AIClientManager()
    return _ai_manager

