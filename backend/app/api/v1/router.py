"""
API v1 路由聚合

所有 v1 版本的 API 路由在此注册
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    test_cases,
    executions,
    tasks,
    environments,
    smart_ops,
    visual_ui,
    design,
    phoenix,
    turbo,
    left_pupil,
    api_engine,
    api_assets,
    data_factory,
    scan_campaigns,
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

# 任务进度追踪 (Celery)
api_router.include_router(
    tasks.router,
    prefix="",  # 根路径下，如 /api/v1/tasks/{id}/progress
    tags=["任务进度"]
)

# 环境管理
api_router.include_router(
    environments.router,
    prefix="/environments",
    tags=["环境管理"]
)

# 智能运维层 (AI Model Governance)
api_router.include_router(
    smart_ops.router,
    prefix="/smart-ops",
    tags=["智能运维"]
)

# 视觉自动化 (Visual UI / RightPupil)
api_router.include_router(
    visual_ui.router,
    prefix="/visual-ui",
    tags=["视觉自动化"]
)

# 需求设计 (Neural Design)
api_router.include_router(
    design.router,
    prefix="/design",
    tags=["需求设计"]
)

# 凤凰仓库 (Phoenix)
api_router.include_router(
    phoenix.router,
    prefix="/phoenix",
    tags=["凤凰仓库"]
)

# Turbo 性能压测
api_router.include_router(
    turbo.router,
    prefix="/turbo",
    tags=["Turbo 压测"]
)

# 左瞳 API 自动化
api_router.include_router(
    left_pupil.router,
    prefix="/left-pupil",
    tags=["左瞳 API 自动化"]
)

# API Engine 兼容接口
api_router.include_router(
    api_engine.router,
    prefix="/api-engine",
    tags=["API Engine 兼容接口"]
)

# API 接口资产库
api_router.include_router(
    api_assets.router,
    prefix="/api-assets",
    tags=["接口资产库"]
)

# 数据工厂
api_router.include_router(
    data_factory.router,
    prefix="/data-factory",
    tags=["数据工厂"]
)

# UI + API 智能扫描 Campaign
api_router.include_router(
    scan_campaigns.router,
    prefix="/scan-campaigns",
    tags=["智能扫描 Campaign"]
)

from app.api.v1.endpoints import dashboard

# 总览大盘 (Dashboard)
api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["总览大盘"]
)
