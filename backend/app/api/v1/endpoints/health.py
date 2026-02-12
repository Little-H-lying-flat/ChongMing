"""
健康检查端点
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str
    services: dict


@router.get("", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
):
    """
    健康检查
    
    返回系统状态和版本信息
    """
    from sqlalchemy import text
    import asyncio
    
    services = {
        "api": "ok",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown",
    }
    overall_status = "healthy"
    
    # 1. 检查数据库 (Timeout 1s)
    try:
        async with asyncio.timeout(1.0):
            await db.execute(text("SELECT 1"))
        services["database"] = "ok"
    except Exception as e:
        services["database"] = "down"
        overall_status = "degraded"
        # logger.error(f"Health Check DB Failed: {e}")

    # 2. 检查 Celery / Redis (通过 Celery Inspect)
    try:
        from app.worker import celery
        # Inspect is sync, but we should wrap it or allow it short timeout
        # Using a simple check if we can get stats
        # Note: inspect() broadcasts to workers, might be slow. 
        # Better: ping Redis directly if possible, or just check celery app connection.
        
        # Simple Broker Connection Check
        async with asyncio.timeout(1.0):
             with celery.connection_or_acquire() as conn:
                 conn.ensure_connection(max_retries=1)
        services["celery"] = "ok"
        services["redis"] = "ok" # Assuming Redis is broker
    except Exception as e:
        services["celery"] = "down"
        services["redis"] = "unknown"
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        timestamp=datetime.now().isoformat(),
        services=services
    )


@router.get("/ping")
async def ping():
    """简单 ping 检查"""
    return {"pong": True}
