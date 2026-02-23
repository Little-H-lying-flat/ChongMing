"""
Dashboard 大盘聚合 API
提供前端大盘页面的统一入口数据
"""

import math
from datetime import datetime, timedelta, UTC
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, text, desc
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.models.execution import Execution, ExecutionStatus
from app.models.environment import Environment

router = APIRouter()

# ================= Schemas =================
class KPIResponse(BaseModel):
    total_executions: int
    global_pass_rate: str
    active_environments: int
    omniparser_status: str
    db_status: str

class TrendData(BaseModel):
    date: str
    passed: int
    failed: int

class DefectData(BaseModel):
    name: str
    value: int

class RecentActivity(BaseModel):
    id: str
    scenario: str
    status: str
    time: str
    duration: str
    error: Optional[str] = None

class DashboardOverviewResponse(BaseModel):
    kpis: KPIResponse
    trend: List[TrendData]
    defects: List[DefectData]
    recent_activities: List[RecentActivity]

# ================= Helper Functions =================
def format_duration(ms: float) -> str:
    """将毫秒格式化为易读的字符串 (如 1m 20s 或 45s)"""
    if not ms:
        return "-"
    seconds = math.ceil(ms / 1000)
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    s = seconds % 60
    return f"{m}m {s}s"

def format_time_ago(dt: datetime) -> str:
    """计算相对时间描述"""
    if not dt:
        return "未知"
    
    # Ensure dt is offset-aware or treat naive as UTC based on standard practice
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
        
    diff = datetime.now(UTC) - dt
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        return f"{int(seconds // 60)} 分钟前"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} 小时前"
    else:
        return f"{int(seconds // 86400)} 天前"

async def check_omni_parser() -> str:
    """简单检测 OmniParser 状态"""
    try:
        import asyncio
        async with asyncio.timeout(1.5):
            async with httpx.AsyncClient(timeout=1.0, trust_env=False) as client:
                # 替换 localhost 为 127.0.0.1 避免 Windows IPv6 DNS 解析带来的 4 秒重试惩罚 (httpx known issue)
                url = f"{settings.OMNIPARSER_URL}/health".replace("localhost", "127.0.0.1")
                resp = await client.get(url)
                return "正常" if resp.status_code == 200 else "异常"
    except Exception:
        return "异常"

# ================= Endpoint =================
@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(db: AsyncSession = Depends(get_db)):
    """
    获取总览大盘数据 (Core Metrics, Trends, Recent Activities)
    """
    # 1. KPIs
    # 1.1 Total Executions & Pass Rate
    # Note: Using SQLAlchemy 2.0 syntax
    total_result = await db.execute(select(func.count(Execution.id)))
    total_executions = total_result.scalar() or 0
    
    passed_result = await db.execute(
        select(func.sum(Execution.passed_cases)).where(Execution.status == ExecutionStatus.PASSED)
    )
    total_passed = passed_result.scalar() or 0
    
    # Estimate global pass rate
    if total_executions == 0:
        global_pass_rate = "100.0%"
    else:
        rate = (total_passed / total_executions) * 100 if total_executions else 100
        # If rate logic needs refinement based on cases instead of execution level, we adjust here.
        # Since we just want an aggregate, we'll do raw count for now.
        status_pass_query = await db.execute(
            select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.PASSED)
        )
        passed_count = status_pass_query.scalar() or 0
        rate = (passed_count / total_executions) * 100
        global_pass_rate = f"{rate:.1f}%"
        
    # 1.2 Active Environments
    env_result = await db.execute(
        select(func.count(Environment.id)).where(Environment.is_active == True)
    )
    active_envs = env_result.scalar() or 0
    
    # 1.3 DB Status
    db_status = "正常"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "异常"
        
    # 1.4 OmniParser Status
    omni_status = await check_omni_parser()
    
    kpis = KPIResponse(
        total_executions=total_executions,
        global_pass_rate=global_pass_rate,
        active_environments=active_envs,
        omniparser_status=omni_status,
        db_status=db_status
    )
    
    # 2. Trend Analysis (Last 7 Days)
    # Get the start of 7 days ago
    end_dt = datetime.now(UTC)
    start_dt = end_dt - timedelta(days=6)
    start_dt = datetime.combine(start_dt.date(), datetime.min.time()).replace(tzinfo=UTC)

    trend_query = select(Execution).where(
        Execution.created_at >= start_dt,
        Execution.status.in_([ExecutionStatus.PASSED, ExecutionStatus.FAILED])
    )
    trend_records = (await db.execute(trend_query)).scalars().all()

    # Pre-fill dictionary with last 7 days (including today)
    trend_map = {}
    for i in range(6, -1, -1):
        target_date = (end_dt - timedelta(days=i)).strftime("%m-%d")
        trend_map[target_date] = {"passed": 0, "failed": 0}

    # Aggregate records
    for record in trend_records:
        record_date = record.created_at.strftime("%m-%d") if record.created_at else None
        if record_date in trend_map:
            if record.status == ExecutionStatus.PASSED:
                trend_map[record_date]["passed"] += 1
            elif record.status == ExecutionStatus.FAILED:
                trend_map[record_date]["failed"] += 1

    trend_data = [
        TrendData(date=k, passed=v["passed"], failed=v["failed"])
        for k, v in trend_map.items()
    ]

    # 3. Defect Analysis (MVP Mock using real failed count)
    failed_eval_query = select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.FAILED)
    failed_count = (await db.execute(failed_eval_query)).scalar() or 0
    
    defects = []
    if failed_count > 0:
        defects = [
            DefectData(name="断言错误", value=int(failed_count * 0.4) or 1),
            DefectData(name="定位器超时", value=int(failed_count * 0.4) or 1),
            DefectData(name="网络连接断开", value=failed_count - (int(failed_count * 0.4) * 2))
        ]

    # 4. Recent Activities (Limit 5)
    recent_query = select(Execution).order_by(desc(Execution.created_at)).limit(5)
    recent_records = (await db.execute(recent_query)).scalars().all()
    
    recent_activities = []
    for record in recent_records:
        error_msg = None
        if record.status in [ExecutionStatus.FAILED, ExecutionStatus.ERROR]:
            # Mock an error message if not present in the record itself.
            # Ideally this comes from the execution config/steps
            error_msg = f"Task {record.id.split('-')[0]} Error"
            
        recent_activities.append(RecentActivity(
            id=record.id,
            scenario=record.config.get("name", f"执行任务 {record.id[:8]}"),
            status=record.status.value,
            time=format_time_ago(record.created_at),
            duration=format_duration(record.duration_ms),
            error=error_msg
        ))
        
    return DashboardOverviewResponse(
        kpis=kpis,
        trend=trend_data,
        defects=defects,
        recent_activities=recent_activities
    )
