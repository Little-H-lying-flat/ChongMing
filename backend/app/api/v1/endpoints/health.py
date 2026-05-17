"""
健康检查端点
"""

from datetime import datetime
import time as _time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.omniparser_health import probe_omniparser_health

router = APIRouter()

# Simple TTL Cache
_health_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 5  # seconds

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
    健康检查（并行 + 缓存）

    - DB / Celery / OmniParser 三项并行检查
    - 结果缓存 5 秒，避免频繁重查
    """
    import asyncio

    now = _time.monotonic()
    if _health_cache["data"] and (now - _health_cache["ts"]) < _CACHE_TTL:
        return _health_cache["data"]

    services: dict = {
        "api": "ok",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown",
    }

    async def check_db():
        try:
            from sqlalchemy import text

            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
            services["database"] = "ok"
        except Exception:
            services["database"] = "down"

    async def check_celery():
        try:

            def _sync_check():
                import redis
                from app.core.config import settings as _s

                r = redis.from_url(
                    _s.CELERY_BROKER_URL,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                )
                r.ping()
                r.close()

            await asyncio.wait_for(asyncio.to_thread(_sync_check), timeout=2.0)
            services["celery"] = "ok"
            services["redis"] = "ok"
        except Exception:
            services["celery"] = "down"
            services["redis"] = "unknown"

    async def check_omniparser():
        if not settings.OMNIPARSER_ENABLED:
            services["omniparser"] = "skipped"
            return
        services["omniparser"] = await probe_omniparser_health(settings.OMNIPARSER_URL)

    await asyncio.gather(
        check_db(),
        check_celery(),
        check_omniparser(),
        return_exceptions=True,
    )

    overall = "healthy" if all(v in {"ok", "skipped"} for k, v in services.items() if k != "redis") else "degraded"

    response = HealthResponse(
        status=overall,
        version=settings.VERSION,
        timestamp=datetime.now().isoformat(),
        services=services,
    )

    _health_cache["data"] = response
    _health_cache["ts"] = _time.monotonic()
    return response


@router.get("/ping")
async def ping():
    """简单 ping 检查"""
    return {"pong": True}
