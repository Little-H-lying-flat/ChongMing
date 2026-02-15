"""
请求日志中间件

结构化请求/响应日志
对应 Issue #AG-004
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from loguru import logger


# 敏感字段列表 (需要脱敏)
SENSITIVE_FIELDS = [
    "password",
    "token",
    "api_key",
    "secret",
    "authorization",
    "cookie",
]


def mask_sensitive_data(data: dict) -> dict:
    """脱敏敏感数据"""
    if not isinstance(data, dict):
        return data
    
    masked = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        if any(field in key_lower for field in SENSITIVE_FIELDS):
            masked[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_data(value)
        else:
            masked[key] = value
    
    return masked


async def request_logging_middleware(request: Request, call_next: Callable):
    """
    请求日志中间件
    
    记录:
    - 请求方法、路径、参数
    - 响应状态码、耗时
    - 错误信息
    
    在 FastAPI 中使用:
        app.middleware("http")(request_logging_middleware)
    """
    # 生成请求 ID
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    
    # 记录开始时间
    start_time = time.time()
    
    # 跳过健康检查等端点的详细日志
    skip_detailed = ["/health", "/docs", "/redoc", "/openapi.json"]
    is_verbose = not any(request.url.path.startswith(p) for p in skip_detailed)
    
    # 请求信息
    if is_verbose:
        logger.info(
            f"[{request_id}] --> {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
    
    # 处理请求
    try:
        response = await call_next(request)
        
        # 计算耗时
        duration = (time.time() - start_time) * 1000
        
        # 响应信息
        if is_verbose:
            logger.info(
                f"[{request_id}] <-- {response.status_code} ({duration:.2f}ms)",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": duration,
                },
            )
        
        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.2f}ms"
        
        return response
        
    except Exception as e:
        # 计算耗时
        duration = (time.time() - start_time) * 1000
        
        # 错误日志
        import traceback
        import sys
        print(traceback.format_exc(), file=sys.stderr)
        logger.error(
            f"[{request_id}] <-- ERROR: {type(e).__name__}: {str(e)} ({duration:.2f}ms)",
            extra={
                "request_id": request_id,
                "error": str(e),
                "duration_ms": duration,
            },
        )
        
        raise


class RequestLogger:
    """
    请求日志类
    
    提供更细粒度的日志控制
    """
    
    def __init__(self, log_body: bool = False, max_body_length: int = 1000):
        self.log_body = log_body
        self.max_body_length = max_body_length
    
    async def log_request(self, request: Request):
        """记录请求详情"""
        request_id = getattr(request.state, "request_id", "unknown")
        
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": mask_sensitive_data(dict(request.headers)),
            "client_ip": request.client.host if request.client else "unknown",
        }
        
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                body = mask_sensitive_data(body)
                body_str = str(body)
                if len(body_str) > self.max_body_length:
                    body_str = body_str[:self.max_body_length] + "..."
                log_data["body"] = body_str
            except:
                pass
        
        logger.debug(f"[{request_id}] Request details", extra=log_data)
    
    async def log_response(
        self,
        request: Request,
        response: Response,
        duration_ms: float,
    ):
        """记录响应详情"""
        request_id = getattr(request.state, "request_id", "unknown")
        
        log_data = {
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "headers": dict(response.headers),
        }
        
        logger.debug(f"[{request_id}] Response details", extra=log_data)
