"""
速率限制中间件

基于 Redis 的 API 限流
对应 Issue #AG-003
"""

from datetime import datetime
from typing import Optional, Tuple

from fastapi import Request, HTTPException, status
from loguru import logger

from app.core.config import settings


class RateLimiter:
    """
    速率限制器
    
    使用滑动窗口算法，基于 Redis 存储
    """
    
    def __init__(
        self,
        redis_url: str = None,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.rpm_limit = requests_per_minute
        self.rph_limit = requests_per_hour
        self._redis = None
    
    async def _get_redis(self):
        """懒加载 Redis 连接"""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception as e:
                logger.warning(f"Redis 连接失败，限流功能禁用: {e}")
                self._redis = False
        return self._redis
    
    async def is_allowed(
        self,
        key: str,
        window_seconds: int = 60,
        max_requests: int = 60,
    ) -> Tuple[bool, int, int]:
        """
        检查是否允许请求
        
        Args:
            key: 限流键 (如 ip:192.168.1.1)
            window_seconds: 时间窗口 (秒)
            max_requests: 最大请求数
            
        Returns:
            Tuple[allowed, remaining, reset_time]
        """
        redis_client = await self._get_redis()
        
        if not redis_client:
            # Redis 不可用，放行
            return True, max_requests, 0
        
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        
        # 使用 Redis 有序集合实现滑动窗口
        pipe = redis_client.pipeline()
        
        # 移除窗口外的记录
        pipe.zremrangebyscore(key, 0, window_start)
        
        # 获取当前窗口内的请求数
        pipe.zcard(key)
        
        # 添加当前请求
        pipe.zadd(key, {str(now): now})
        
        # 设置过期时间
        pipe.expire(key, window_seconds)
        
        results = await pipe.execute()
        current_count = results[1]
        
        remaining = max(0, max_requests - current_count - 1)
        reset_time = int(now + window_seconds)
        
        if current_count >= max_requests:
            return False, 0, reset_time
        
        return True, remaining, reset_time
    
    async def check_rate_limit(
        self,
        request: Request,
        user_id: Optional[str] = None,
    ):
        """
        检查请求速率限制
        
        优先使用用户 ID，否则使用 IP
        """
        # 确定限流键
        if user_id:
            key = f"rate_limit:user:{user_id}"
            limit = self.rpm_limit * 2  # 登录用户限制翻倍
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"rate_limit:ip:{client_ip}"
            limit = self.rpm_limit
        
        allowed, remaining, reset_time = await self.is_allowed(
            key=key,
            window_seconds=60,
            max_requests=limit,
        )
        
        # 添加响应头
        request.state.rate_limit_remaining = remaining
        request.state.rate_limit_reset = reset_time
        
        if not allowed:
            logger.warning(f"速率限制触发: {key}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(60),
                },
            )


# 全局限流器实例
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    速率限制中间件
    
    在 FastAPI 中使用:
        app.middleware("http")(rate_limit_middleware)
    """
    # 跳过健康检查等端点
    skip_paths = ["/health", "/docs", "/redoc", "/openapi.json"]
    if any(request.url.path.startswith(p) for p in skip_paths):
        return await call_next(request)
    
    # 获取用户 ID (如果已认证)
    user_id = getattr(request.state, "user_id", None)
    
    # 检查限流
    await rate_limiter.check_rate_limit(request, user_id)
    
    # 继续处理请求
    response = await call_next(request)
    
    # 添加限流响应头
    if hasattr(request.state, "rate_limit_remaining"):
        response.headers["X-RateLimit-Remaining"] = str(
            request.state.rate_limit_remaining
        )
        response.headers["X-RateLimit-Reset"] = str(
            request.state.rate_limit_reset
        )
    
    return response
