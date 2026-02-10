"""
API v1 路由聚合

所有 v1 版本的 API 路由在此注册
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    test_cases,
    executions,
    design,
    phoenix,
    tasks,
    api_engine,
    environments,
    data_factory,
    left_pupil,
)

api_router = APIRouter()

# 健康检查
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["健康检查"]
)

# 测试用例管理
api_router.include_router(
    test_cases.router,
    prefix="/test-cases",
    tags=["测试用例"]
)

# 执行管理
api_router.include_router(
    executions.router,
    prefix="/executions",
    tags=["执行管理"]
)

# 神经设计层
api_router.include_router(
    design.router,
    prefix="/design",
    tags=["神经设计层"]
)

# 凤凰涅槃层
api_router.include_router(
    phoenix.router,
    prefix="/phoenix",
    tags=["凤凰涅槃层"]
)

# 任务进度追踪 (Celery)
api_router.include_router(
    tasks.router,
    prefix="",  # 根路径下，如 /api/v1/tasks/{id}/progress
    tags=["任务进度"]
)

# 左瞳引擎 (API 测试)
api_router.include_router(
    api_engine.router,
    prefix="/api-engine",
    tags=["左瞳引擎"]
)

# 环境管理
api_router.include_router(
    environments.router,
    prefix="/environments",
    tags=["环境管理"]
)

# 数据工厂
api_router.include_router(
    data_factory.router,
    prefix="/data-factory",
    tags=["数据工厂"]
)

# 左瞳引擎 v2 (API 测试)
api_router.include_router(
    left_pupil.router,
    prefix="/left-pupil",
    tags=["左瞳引擎"]
)
