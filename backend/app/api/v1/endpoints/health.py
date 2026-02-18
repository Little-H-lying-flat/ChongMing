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

# ─── Simple TTL Cache ───
import time as _time
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
    
    - DB / Celery / OmniParser 三项检查并行执行
    - 结果缓存 5 秒，避免频繁重查
    """
    import asyncio

    # ─── 缓存命中 ───
    now = _time.monotonic()
    if _health_cache["data"] and (now - _health_cache["ts"]) < _CACHE_TTL:
        return _health_cache["data"]

    services: dict = {
        "api": "ok",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown",
    }

    # ─── 单项检查函数 ───
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
                """
                直接用 redis-py ping，比 Kombu ensure_connection 快 100x。
                Kombu 需要 AMQP 协议协商 (4s+)，但我们只需知道 Redis 是否可达。
                """
                import redis
                from app.core.config import settings as _s
                # 解析 broker URL: redis://localhost:6379/0
                r = redis.from_url(_s.CELERY_BROKER_URL, socket_timeout=1.0, socket_connect_timeout=1.0)
                r.ping()  # ~5ms
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
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{settings.OMNIPARSER_URL}/health")
                if response.status_code == 200:
                    services["omniparser"] = "ok"
                else:
                    services["omniparser"] = "loading"
        except Exception:
            services["omniparser"] = "down"

    # ─── 并行执行所有检查 ───
    await asyncio.gather(
        check_db(),
        check_celery(),
        check_omniparser(),
        return_exceptions=True
    )

    overall = "healthy" if all(
        v == "ok" for k, v in services.items() if k != "redis"
    ) else "degraded"

    response = HealthResponse(
        status=overall,
        version=settings.VERSION,
        timestamp=datetime.now().isoformat(),
        services=services
    )

    # ─── 更新缓存 ───
    _health_cache["data"] = response
    _health_cache["ts"] = _time.monotonic()

    return response


@router.get("/ping")
async def ping():
    """简单 ping 检查"""
    return {"pong": True}
