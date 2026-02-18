"""
Smart Ops API 端点

AI 模型配置管理
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.ai_models import AVAILABLE_MODELS
from app.services.smart_ops.ai_config_service import AIConfigService

router = APIRouter(tags=["Flow 6: Smart Ops (模型治理)"])


# --- Schemas ---

class AIModelSchema(BaseModel):
    """AI 模型信息"""
    model_id: str = Field(..., description="模型唯一标识", example="gpt-4-turbo")
    provider: str = Field(..., description="供应商 (openai, azure, anthropic)", example="openai")
    capability: str = Field(..., description="能力类型 (chat, embedding, vision)", example="chat")
    description: str = Field(..., description="模型描述")
    cost_per_1k_tokens: float = Field(..., description="每千 Token 成本 ($)", example=0.01)


class AIModuleConfigSchema(BaseModel):
    """模块配置信息"""
    module: str = Field(..., description="业务模块名称 (planning, coding, reviewing)", example="planning")
    model_id: str = Field(..., description="当前使用的模型 ID", example="gpt-4-turbo")
    provider: str = Field(..., description="供应商", example="openai")
    temperature: Optional[float] = Field(None, description="模型温度 (0.0 - 2.0)", example=0.7)
    max_tokens: Optional[int] = Field(None, description="最大输出 Token 数", example=4096)
    is_custom: bool = Field(False, description="是否是自定义配置")


class UpdateAIConfigRequest(BaseModel):
    """更新配置请求"""
    module: str = Field(..., description="目标业务模块", example="planning")
    model_id: str = Field(..., description="指定模型 ID", example="gpt-3.5-turbo")
    temperature: Optional[float] = Field(None, description="覆盖温度设置")
    max_tokens: Optional[int] = Field(None, description="覆盖 Max Tokens")


# --- Endpoints ---

@router.get(
    "/models", 
    response_model=List[AIModelSchema],
    summary="支持模型列表 (List Models)",
    description="获取平台当前支持的所有 AI 模型及其计费信息。",
)
async def list_available_models():
    """List all supported AI models"""
    models = []
    for m in AVAILABLE_MODELS.values():
        models.append(AIModelSchema(
            model_id=m.model_id,
            provider=m.provider.value,
            capability=m.capability.value,
            description=m.description,
            cost_per_1k_tokens=m.cost_per_1k_tokens,
        ))
    return models


@router.get(
    "/config", 
    response_model=List[AIModuleConfigSchema],
    summary="模块模型配置 (Get Module Configs)",
    description="获取各个业务模块 (Planning, Coding 等) 当前绑定的模型配置。",
)
async def get_module_configs():
    """Get current configuration for all modules"""
    configs = await AIConfigService.get_all_module_configs()
    return [AIModuleConfigSchema(**c) for c in configs]


@router.post(
    "/config", 
    response_model=AIModuleConfigSchema,
    summary="更新模型映射 (Update Config)",
    description="""
    **Flow 6 核心接口**: 为特定业务模块指定 AI 模型。
    
    - **用途**: 动态调整模型策略 (如由 GPT-4 降级到 GPT-3.5 以节省成本)。
    - **生效**: 配置即时生效 (Redis 缓存更新)。
    """
)
async def update_module_config(request: UpdateAIConfigRequest):
    """Update model mapping for a module"""
    try:
        result = await AIConfigService.update_module_config_db(
            module=request.module,
            model_id=request.model_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return AIModuleConfigSchema(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/provider",
    summary="配置供应商密钥 (Update Provider Key)",
    description="**安全接口**: 更新 AI 供应商 (OpenAI, Azure) 的 API Key 和 Base URL。",
)
class ProviderConfigSchema(BaseModel):
    provider: str = Field(..., description="供应商名称", example="openai")
    api_key: str = Field(..., description="API Key (将加密存储)")
    base_url: Optional[str] = Field(None, description="Base URL (可选)")


@router.post(
    "/provider",
    summary="配置供应商密钥 (Update Provider Key)",
    description="**安全接口**: 更新 AI 供应商 (OpenAI, Azure) 的 API Key 和 Base URL。",
)
async def update_provider_config(config: ProviderConfigSchema):
    """
    Update API Key for a provider

    NOTE: In a real prod app, encrypt api_key before storing!
    """
    return await AIConfigService.update_provider_config_db(config.provider, config.api_key, config.base_url)


@router.post(
    "/cache/clear",
    summary="清除配置缓存 (Clear Cache)",
    description="强制清除 Redis 中的 AI 配置缓存，从数据库重新加载。",
)
async def clear_cache():
    """Manually clear config cache"""
    AIConfigService.clear_cache()
    return {"status": "success", "message": "Cache cleared"}
