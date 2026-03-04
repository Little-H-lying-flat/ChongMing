"""Smart Ops API endpoints."""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_models import AVAILABLE_MODELS
from app.core.database import get_db
from app.models.defect import DefectRecord
from app.services.smart_ops.ai_config_service import AIConfigService
from app.services.smart_ops.defect_manager import DefectManager

router = APIRouter(tags=["Flow 6: Smart Ops"])
defect_manager_instance = DefectManager()


class AIModelSchema(BaseModel):
    model_id: str = Field(..., description="Model ID")
    provider: str = Field(..., description="Provider")
    capability: str = Field(..., description="Capability")
    description: str = Field(..., description="Description")
    cost_per_1k_tokens: float = Field(..., description="Cost per 1k tokens")


class AIModuleConfigSchema(BaseModel):
    module: str = Field(..., description="Business module")
    model_id: str = Field(..., description="Model ID")
    provider: str = Field(..., description="Provider")
    temperature: Optional[float] = Field(None, description="Temperature")
    max_tokens: Optional[int] = Field(None, description="Max tokens")
    is_custom: bool = Field(False, description="Whether custom config")


class UpdateAIConfigRequest(BaseModel):
    module: str = Field(..., description="Target module")
    model_id: str = Field(..., description="Target model")
    temperature: Optional[float] = Field(None, description="Temperature override")
    max_tokens: Optional[int] = Field(None, description="Max token override")


class ProviderConfigSchema(BaseModel):
    provider: str = Field(..., description="Provider name")
    api_key: str = Field(..., description="Provider API key")
    base_url: Optional[str] = Field(None, description="Provider base URL")


class DefectAnalysisRequest(BaseModel):
    error_msg: str = Field(..., description="Raw error message")
    context: Optional[str] = Field(None, description="Optional context")


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


@router.get("/models", response_model=List[AIModelSchema], summary="List Models")
async def list_available_models() -> List[AIModelSchema]:
    models: List[AIModelSchema] = []
    for model in AVAILABLE_MODELS.values():
        models.append(
            AIModelSchema(
                model_id=model.model_id,
                provider=model.provider.value,
                capability=model.capability.value,
                description=model.description,
                cost_per_1k_tokens=model.cost_per_1k_tokens,
            )
        )
    return models


@router.get("/config", response_model=List[AIModuleConfigSchema], summary="Get Module Configs")
async def get_module_configs() -> List[AIModuleConfigSchema]:
    configs = await AIConfigService.get_all_module_configs()
    return [AIModuleConfigSchema(**cfg) for cfg in configs]


@router.post("/config", response_model=AIModuleConfigSchema, summary="Update Config")
async def update_module_config(request: UpdateAIConfigRequest) -> AIModuleConfigSchema:
    try:
        result = await AIConfigService.update_module_config_db(
            module=request.module,
            model_id=request.model_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return AIModuleConfigSchema(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/provider", summary="Update Provider Key")
async def update_provider_config(config: ProviderConfigSchema) -> dict:
    return await AIConfigService.update_provider_config_db(
        config.provider,
        config.api_key,
        config.base_url,
    )


@router.post("/cache/clear", summary="Clear Config Cache")
async def clear_cache() -> dict:
    AIConfigService.clear_cache()
    return {"status": "success", "message": "Cache cleared"}


@router.get("/metrics/tokens", summary="Get Token Metrics")
async def get_token_metrics(days: int = 7) -> Any:
    return await AIConfigService.get_token_metrics(days=days)


@router.post(
    "/analyze-defect",
    response_model=DefectAnalysisResponse,
    summary="Analyze Defect",
)
async def analyze_defect(req: DefectAnalysisRequest) -> DefectAnalysisResponse:
    await defect_manager_instance.connect()
    analysis_result = await defect_manager_instance.analyze_root_cause(
        error_msg=req.error_msg,
        context=req.context,
    )
    similar_defects = await defect_manager_instance.find_similar_defect(req.error_msg)
    return DefectAnalysisResponse(
        analysis=analysis_result,
        similar_defects=similar_defects,
    )


@router.get(
    "/defects",
    response_model=List[DefectRecordResponse],
    summary="Get Historical Defects",
)
async def get_historical_defects(db: AsyncSession = Depends(get_db)) -> List[DefectRecordResponse]:
    stmt = select(DefectRecord).order_by(DefectRecord.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [DefectRecordResponse.model_validate(record) for record in records]


@router.post(
    "/defects",
    response_model=DefectRecordResponse,
    summary="Save Defect Analysis",
)
async def save_defect_analysis(req: dict, db: AsyncSession = Depends(get_db)) -> DefectRecordResponse:
    error_msg = req.get("error_msg")
    root_cause = req.get("root_cause")
    suggested_fix = req.get("suggested_fix")

    if not all([error_msg, root_cause, suggested_fix]):
        raise HTTPException(status_code=400, detail="Missing required parameters")

    new_record = DefectRecord(
        error_msg=error_msg,
        root_cause=root_cause,
        suggested_fix=suggested_fix,
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)

    await defect_manager_instance.connect()
    await defect_manager_instance.store_defect(
        error_msg=error_msg,
        root_cause=root_cause,
        solution=suggested_fix,
    )

    return DefectRecordResponse.model_validate(new_record)
