"""
数据工厂 API 端点

对应 Issue #DF-003
- POST /data-factory/generate - 生成测试数据
- GET /data-factory/records/{id} - 获取数据记录
- DELETE /data-factory/cleanup - 清理数据
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.data_factory import DataFactory


router = APIRouter()


# ========== Schemas ==========

class FieldDefinition(BaseModel):
    """字段定义"""
    type: str = "string"
    options: dict = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    """生成数据请求"""
    schema_name: str = Field(..., min_length=1, max_length=100)
    schema: dict[str, str | FieldDefinition]
    count: int = Field(default=1, ge=1, le=1000)
    ttl_seconds: Optional[int] = Field(default=None, ge=60)
    execution_id: Optional[str] = None
    environment_id: Optional[str] = None
    locale: str = "zh_CN"


class CleanupRequest(BaseModel):
    """清理请求"""
    batch_id: Optional[str] = None
    cleanup_expired: bool = True
    delete_old_days: Optional[int] = Field(default=None, ge=1)


class GenerateResponse(BaseModel):
    """生成响应"""
    record_id: str
    batch_id: str
    count: int
    data: list[dict]


# ========== Endpoints ==========

@router.post("/generate", response_model=GenerateResponse)
async def generate_data(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """根据 Schema 生成测试数据"""
    factory = DataFactory(db, locale=request.locale)
    
    # 转换 schema 格式
    schema = {}
    for field_name, field_def in request.schema.items():
        if isinstance(field_def, str):
            schema[field_name] = field_def
        else:
            schema[field_name] = field_def.model_dump()
    
    record = await factory.generate_and_save(
        schema_name=request.schema_name,
        schema=schema,
        count=request.count,
        ttl_seconds=request.ttl_seconds,
        execution_id=request.execution_id,
        environment_id=request.environment_id,
    )
    
    return GenerateResponse(
        record_id=record.id,
        batch_id=record.batch_id,
        count=record.count,
        data=record.data.get("items", []),
    )


@router.get("/records/{record_id}")
async def get_data_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取数据记录"""
    factory = DataFactory(db)
    record = await factory.get_record(record_id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"记录 '{record_id}' 不存在",
        )
    
    return {
        "id": record.id,
        "schema_name": record.schema_name,
        "batch_id": record.batch_id,
        "count": record.count,
        "status": record.status.value,
        "data": record.data.get("items", []),
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "created_at": record.created_at.isoformat(),
    }


@router.delete("/cleanup")
async def cleanup_data(
    request: CleanupRequest,
    db: AsyncSession = Depends(get_db),
):
    """清理测试数据"""
    factory = DataFactory(db)
    results = {"expired": 0, "batch": 0, "deleted": 0}
    
    if request.batch_id:
        results["batch"] = await factory.cleanup_by_batch(request.batch_id)
    
    if request.cleanup_expired:
        results["expired"] = await factory.cleanup_expired()
    
    if request.delete_old_days:
        results["deleted"] = await factory.delete_cleaned(request.delete_old_days)
    
    return {"message": "清理完成", "results": results}


@router.get("/schemas")
async def list_available_schemas():
    """列出可用的字段类型"""
    from app.services.data_factory import SCHEMA_GENERATORS
    
    return {
        "available_types": list(SCHEMA_GENERATORS.keys()),
        "special_types": ["enum", "range", "pattern", "fixed"],
    }
