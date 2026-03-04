"""
健康检查端点
"""

from datetime import datetime
import time as _time

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()

# Simple TTL Cache
_health_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 5  # seconds

# OmniParser health probe tuning: avoid false negatives when probe latency is ~1.2-1.5s.
_OMNIPARSER_TOTAL_TIMEOUT = 3.5
_OMNIPARSER_CONNECT_TIMEOUT = 1.0
_OMNIPARSER_READ_TIMEOUT = 2.5


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

            async with asyncio.timeout(2.0):
                await db.execute(text("SELECT 1"))
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
        try:
            import httpx

            url = f"{settings.OMNIPARSER_URL}/health".replace("localhost", "127.0.0.1")
            timeout = httpx.Timeout(
                connect=_OMNIPARSER_CONNECT_TIMEOUT,
                read=_OMNIPARSER_READ_TIMEOUT,
                write=_OMNIPARSER_READ_TIMEOUT,
                pool=_OMNIPARSER_CONNECT_TIMEOUT,
            )
            async with asyncio.timeout(_OMNIPARSER_TOTAL_TIMEOUT):
                async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                    response = await client.get(url)
                    services["omniparser"] = "ok" if response.status_code == 200 else "loading"
        except Exception as exc:
            logger.warning(f"OmniParser health check failed: {exc}")
            services["omniparser"] = "down"

    await asyncio.gather(
        check_db(),
        check_celery(),
        check_omniparser(),
        return_exceptions=True,
    )

    overall = "healthy" if all(v == "ok" for k, v in services.items() if k != "redis") else "degraded"

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
