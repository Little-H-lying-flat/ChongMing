"""
重明 (ChongMing) - FastAPI 主入口

启动方式:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import sys
import asyncio

# === Windows AsyncIO Fix (MUST BE FIRST) ===
# Fixes NotImplementedError in Playwright/Subprocess on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.router import api_router
from app.worker import celery  # Ensure Celery app is loaded

# nest_asyncio removed to prevent conflict with ProactorLoop
# from app.worker import celery  # Ensure Celery app is loaded



@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Startup
    setup_logging()
    
    # Initialize DB (Create tables if not exist)
    from app.core.database import init_db
    await init_db()
    
    logger.info(f"🐦 重明 v{settings.VERSION} 启动中...")
    logger.info(f"📡 API 文档: http://localhost:{settings.PORT}/docs")

    # 初始化 AI Client Manager (Dependency Injection)
    # 解决 Core <-> Services 循环依赖
    from app.core.ai_client import init_ai_manager
    from app.services.smart_ops.ai_config_provider_impl import AIConfigProviderImpl
    
    init_ai_manager(AIConfigProviderImpl())
    logger.info("🧠 AI Client Manager initialized with Service Provider")

    
    yield
    
    # Shutdown
    logger.info("🔥 重明关闭中...")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="重明 (ChongMing)",
        description="AI Agent 驱动的自动化质量工程平台",
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # 请求日志中间件 (最先添加，最后执行)
    from app.core.request_logger import request_logging_middleware
    app.middleware("http")(request_logging_middleware)
    
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(api_router, prefix="/api/v1")
    
    return app


# 导出应用实例
app = create_app()


def main():
    """命令行入口"""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
