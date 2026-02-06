"""
健康检查端点
"""

from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str
    services: dict


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    健康检查
    
    返回系统状态和版本信息
    """
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        timestamp=datetime.now().isoformat(),
        services={
            "api": "ok",
            "database": "pending",  # TODO: 实际检查
            "redis": "pending",     # TODO: 实际检查
            "celery": "pending",    # TODO: 实际检查
        }
    )


@router.get("/ping")
async def ping():
    """简单 ping 检查"""
    return {"pong": True}
