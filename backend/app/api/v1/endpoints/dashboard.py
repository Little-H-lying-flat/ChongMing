"""
Dashboard overview endpoint.
Provides aggregate metrics for frontend overview page.
"""

import math
from datetime import UTC, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.defect import DefectRecord
from app.models.environment import Environment
from app.models.execution import Execution, ExecutionStatus
from app.services.omniparser_health import probe_omniparser_health

router = APIRouter()

STATUS_OK = "\u6b63\u5e38"
STATUS_ERR = "\u5f02\u5e38"
DEFECT_PENDING_LABEL = "\u5f85\u667a\u80fd\u6392\u67e5\u7f3a\u9677"


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


def format_duration(ms: float) -> str:
    if not ms:
        return "-"
    seconds = math.ceil(ms / 1000)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"


def format_time_ago(dt: datetime) -> str:
    if not dt:
        return "\u672a\u77e5"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    diff = datetime.now(UTC) - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "\u521a\u521a"
    if seconds < 3600:
        return f"{int(seconds // 60)} \u5206\u949f\u524d"
    if seconds < 86400:
        return f"{int(seconds // 3600)} \u5c0f\u65f6\u524d"
    return f"{int(seconds // 86400)} \u5929\u524d"


async def check_omni_parser() -> str:
    probe_status = await probe_omniparser_health(settings.OMNIPARSER_URL)
    return STATUS_OK if probe_status == "ok" else STATUS_ERR


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(db: AsyncSession = Depends(get_db)):
    # 1) KPI
    total_executions = (await db.execute(select(func.count(Execution.id)))).scalar() or 0

    passed_count = (
        await db.execute(select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.PASSED))
    ).scalar() or 0
    global_pass_rate = "100.0%" if total_executions == 0 else f"{(passed_count / total_executions) * 100:.1f}%"

    active_envs = (
        await db.execute(select(func.count(Environment.id)).where(Environment.is_active.is_(True)))
    ).scalar() or 0

    db_status = STATUS_OK
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = STATUS_ERR

    omni_status = await check_omni_parser()

    kpis = KPIResponse(
        total_executions=total_executions,
        global_pass_rate=global_pass_rate,
        active_environments=active_envs,
        omniparser_status=omni_status,
        db_status=db_status,
    )

    # 2) Trend (last 7 days)
    end_dt = datetime.now(UTC)
    start_dt = datetime.combine((end_dt - timedelta(days=6)).date(), datetime.min.time()).replace(tzinfo=UTC)

    trend_records = (
        await db.execute(
            select(Execution).where(
                Execution.created_at >= start_dt,
                Execution.status.in_([ExecutionStatus.PASSED, ExecutionStatus.FAILED]),
            )
        )
    ).scalars().all()

    trend_map = {}
    for i in range(6, -1, -1):
        key = (end_dt - timedelta(days=i)).strftime("%m-%d")
        trend_map[key] = {"passed": 0, "failed": 0}

    for record in trend_records:
        key = record.created_at.strftime("%m-%d") if record.created_at else None
        if key in trend_map:
            if record.status == ExecutionStatus.PASSED:
                trend_map[key]["passed"] += 1
            elif record.status == ExecutionStatus.FAILED:
                trend_map[key]["failed"] += 1

    trend_data = [TrendData(date=k, passed=v["passed"], failed=v["failed"]) for k, v in trend_map.items()]

    # 3) Defects
    defect_records = (await db.execute(select(DefectRecord.root_cause))).scalars().all()
    defects: List[DefectData] = []

    if defect_records:
        category_counts = {
            "UI\u5b9a\u4f4d/\u53ef\u89c1\u6027\u5f02\u5e38": 0,
            "\u65ad\u8a00\u5931\u8d25(\u72b6\u6001\u7801/\u8fd4\u56de\u503c)": 0,
            "\u7f51\u7edc\u6216\u8fde\u63a5\u670d\u52a1\u5f02\u5e38": 0,
            "\u8d85\u65f6\u4e0e\u7b49\u5f85\u6302\u8d77": 0,
            "\u73af\u5883\u6216\u9274\u6743\u5f02\u5e38": 0,
            "\u5176\u4ed6\u672a\u77e5\u7c7b\u578b": 0,
        }

        for cause in defect_records:
            rc = (cause or "").lower()
            if any(k in rc for k in ["\u5b9a\u4f4d", "locator", "\u5143\u7d20", "element", "\u53ef\u89c1"]):
                category_counts["UI\u5b9a\u4f4d/\u53ef\u89c1\u6027\u5f02\u5e38"] += 1
            elif any(k in rc for k in ["\u65ad\u8a00", "assert", "status", "\u671f\u671b", "\u4e0d\u5339\u914d"]):
                category_counts["\u65ad\u8a00\u5931\u8d25(\u72b6\u6001\u7801/\u8fd4\u56de\u503c)"] += 1
            elif any(k in rc for k in ["\u7f51\u7edc", "\u8fde\u63a5", "refused", "502", "gateway"]):
                category_counts["\u7f51\u7edc\u6216\u8fde\u63a5\u670d\u52a1\u5f02\u5e38"] += 1
            elif any(k in rc for k in ["\u8d85\u65f6", "timeout", "\u7b49\u5f85", "\u6302\u8d77"]):
                category_counts["\u8d85\u65f6\u4e0e\u7b49\u5f85\u6302\u8d77"] += 1
            elif any(k in rc for k in ["\u8ba4\u8bc1", "token", "401", "403", "\u9274\u6743"]):
                category_counts["\u73af\u5883\u6216\u9274\u6743\u5f02\u5e38"] += 1
            else:
                category_counts["\u5176\u4ed6\u672a\u77e5\u7c7b\u578b"] += 1

        defects = [DefectData(name=k, value=v) for k, v in category_counts.items() if v > 0]
        defects.sort(key=lambda x: x.value, reverse=True)
    else:
        failed_count = (
            await db.execute(select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.FAILED))
        ).scalar() or 0
        if failed_count > 0:
            defects = [DefectData(name=DEFECT_PENDING_LABEL, value=failed_count)]

    # 4) Recent activities
    recent_records = (
        await db.execute(select(Execution).order_by(desc(Execution.created_at)).limit(5))
    ).scalars().all()

    recent_activities = []
    for record in recent_records:
        error_msg = None
        if record.status in [ExecutionStatus.FAILED, ExecutionStatus.ERROR]:
            error_msg = f"Task {record.id.split('-')[0]} Error"

        recent_activities.append(
            RecentActivity(
                id=record.id,
                scenario=record.config.get("name", f"\u6267\u884c\u4efb\u52a1 {record.id[:8]}"),
                status=record.status.value,
                time=format_time_ago(record.created_at),
                duration=format_duration(record.duration_ms),
                error=error_msg,
            )
        )

    return DashboardOverviewResponse(
        kpis=kpis,
        trend=trend_data,
        defects=defects,
        recent_activities=recent_activities,
    )
