"""
Smart Ops API 端点

AI 模型配置管理
"""

from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.ai_models import AVAILABLE_MODELS
from app.services.smart_ops.ai_config_service import AIConfigService
from app.services.smart_ops.defect_manager import DefectManager
from app.models.defect import DefectRecord

router = APIRouter(tags=["Flow 6: Smart Ops (模型治理与智能运维)"])

# Shared Defect Manager Instance (Singleton-like pattern for connection reuse)
defect_manager_instance = DefectManager()


# --- Schemas ---

class AIModelSchema(BaseModel):
    """AI 模型信息"""
    model_id: str = Field(..., description="模型唯一标识", json_schema_extra={"example": "gpt-4-turbo"})
    provider: str = Field(..., description="供应商 (openai, azure, anthropic)", json_schema_extra={"example": "openai"})
    capability: str = Field(..., description="能力类型 (chat, embedding, vision)", json_schema_extra={"example": "chat"})
    description: str = Field(..., description="模型描述")
    cost_per_1k_tokens: float = Field(..., description="每千 Token 成本 ($)", json_schema_extra={"example": 0.01})


class AIModuleConfigSchema(BaseModel):
    """模块配置信息"""
    module: str = Field(..., description="业务模块名称 (planning, coding, reviewing)", json_schema_extra={"example": "planning"})
    model_id: str = Field(..., description="当前使用的模型 ID", json_schema_extra={"example": "gpt-4-turbo"})
    provider: str = Field(..., description="供应商", json_schema_extra={"example": "openai"})
    temperature: Optional[float] = Field(None, description="模型温度 (0.0 - 2.0)", json_schema_extra={"example": 0.7})
    max_tokens: Optional[int] = Field(None, description="最大输出 Token 数", json_schema_extra={"example": 4096})
    is_custom: bool = Field(False, description="是否是自定义配置")


class UpdateAIConfigRequest(BaseModel):
    """更新配置请求"""
    module: str = Field(..., description="目标业务模块", json_schema_extra={"example": "planning"})
    model_id: str = Field(..., description="指定模型 ID", json_schema_extra={"example": "gpt-3.5-turbo"})
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
    provider: str = Field(..., description="供应商名称", json_schema_extra={"example": "openai"})
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


@router.get(
    "/metrics/tokens",
    summary="获取模型 Token 消耗指标",
    description="获取过去 N 天各大模型的 Token 消耗量与预估成本。",
)
async def get_token_metrics(days: int = 7):
    """
    Get token usage metrics for the last N days.
    Returns: List of {"date": "YYYY-MM-DD", "model_id": tokens, "cost": total_cost}
    """
    return await AIConfigService.get_token_metrics(days=days)


# --- Smart Ops: Defect Root Cause Analysis (缺陷分析与自愈) ---

class DefectAnalysisRequest(BaseModel):
    error_msg: str = Field(..., description="The raw error message from the failed test")
    context: Optional[str] = Field(None, description="Optional context: DOM snapshot, code snippet, etc")


class DefectRecordResponse(BaseModel):
    id: int
    execution_step_id: Optional[int]
    error_msg: str
    root_cause: str
    suggested_fix: str
    created_at: Any
    
    class Config:
        from_attributes = True

class DefectAnalysisResponse(BaseModel):
    analysis: dict
    similar_defects: List[dict]


@router.post(
    "/analyze-defect",
    response_model=DefectAnalysisResponse,
    summary="AI 自动根因诊断 (Analyze Defect)",
    description="利用大模型分析报错日志，诊断失败原因（如加载超时、定位器失效、接口报错），并进行 Milvus 向量相似度查询寻找历史类似 Bug。"
)
async def analyze_defect(req: DefectAnalysisRequest):
    """Run AI Analysis on a defect log and perform semantic similarity search"""
    # 1. Connect to Vector Store if not already connected
    await defect_manager_instance.connect()
    
    # 2. Perform AI Root Cause Extraction
    analysis_result = await defect_manager_instance.analyze_root_cause(
        error_msg=req.error_msg,
        context=req.context
    )
    
    # 3. Retrieve Historical Similar Defects from Milvus
    similar_defects = await defect_manager_instance.find_similar_defect(req.error_msg)
    
    return {
        "analysis": analysis_result,
        "similar_defects": similar_defects
    }


@router.get(
    "/defects",
    response_model=List[DefectRecordResponse],
    summary="获取缺陷池 (Get Historical Defects)",
    description="获取历史所有大模型诊断过的缺陷库记录。"
)
async def get_historical_defects(db: AsyncSession = Depends(get_db)):
    """Fetch the historic defect DB table"""
    stmt = select(DefectRecord).order_by(DefectRecord.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return records


@router.post(
    "/defects",
    response_model=DefectRecordResponse,
    summary="收录为历史缺陷 (Save Defect Analysis)",
    description="将经过验证的缺陷和根因报告持久化存入关系型数据库与 Milvus 向量库，供下次检索兜底使用。"
)
async def save_defect_analysis(req: dict, db: AsyncSession = Depends(get_db)):
    """
    Save the final validated defect analysis into the DB (for UI retrieval)
    and Milvus (for future AI retrieval).
    """
    error_msg = req.get("error_msg")
    root_cause = req.get("root_cause")
    suggested_fix = req.get("suggested_fix")
    
    if not all([error_msg, root_cause, suggested_fix]):
         raise HTTPException(status_code=400, detail="Missing required parameters")
         
    # 1. Save to DB
    new_record = DefectRecord(
        error_msg=error_msg,
        root_cause=root_cause,
        suggested_fix=suggested_fix
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    
    # 2. Ensure Milvus Connection and Store Vector
    await defect_manager_instance.connect()
    await defect_manager_instance.store_defect(
        error_msg=error_msg, 
        root_cause=root_cause, 
        solution=suggested_fix
    )
    
    return new_record
