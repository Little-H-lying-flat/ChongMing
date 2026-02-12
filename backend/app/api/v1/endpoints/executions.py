"""
执行管理端点

测试执行的启动、监控和结果查询
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from celery.result import AsyncResult
import uuid

from app.engines.right_pupil import RightPupilEngine
from app.tasks.execution_tasks import execute_test_cases, cancel_execution as cancel_task

router = APIRouter()


# ===================== 数据模型 =====================

class UiRunRequest(BaseModel):
    prompt: str
    url: str


class ExecutionRequest(BaseModel):
    """执行请求"""
    tc_ids: List[str] = Field(..., description="测试用例 ID 列表")
    mode: str = Field("normal", description="执行模式: normal, debug, fast")
    parallel: bool = Field(True, description="是否并行执行")
    max_workers: int = Field(5, ge=1, le=20, description="最大并行数")
    env: Optional[str] = Field(None, description="目标环境")


class ExecutionResponse(BaseModel):
    """执行响应"""
    execution_id: str
    status: str
    total_cases: int
    dashboard_url: str


class ExecutionStatus(BaseModel):
    """执行状态"""
    execution_id: str
    status: str
    progress: float
    passed: int
    failed: int
    skipped: int
    running: int
    pending: int
    start_time: str
    elapsed_seconds: float


class ExecutionResult(BaseModel):
    """执行结果"""
    execution_id: str
    status: str
    summary: dict
    cases: List[dict]
    duration_seconds: float
    report_url: Optional[str]


# ===================== API 端点 =====================

@router.post("", response_model=ExecutionResponse, status_code=202)
async def start_execution(
    request: ExecutionRequest,
    background_tasks: BackgroundTasks,
):
    """
    启动测试执行
    
    将 TC-IR 分发到执行引擎，返回执行 ID
    """
    # 生成执行 ID (虽然 Task 会生成，但我们这里预生成以便返回，或者让 Task 返回)
    # 策略：由 Task 生成 ID 比较麻烦，因为 .delay() 返回的是 Task ID。
    # 我们使用 Task ID 作为 Execution ID，或者在 Task 内部生成业务 ID。
    # 这里为了简单，我们使用 Task ID 作为 Execution ID。
    
    task = execute_test_cases.delay(
        tc_ids=request.tc_ids,
        config={
            "mode": request.mode,
            "parallel": request.parallel,
            "max_workers": request.max_workers,
            "env": request.env
        }
    )
    
    return ExecutionResponse(
        execution_id=task.id,
        status="pending",
        total_cases=len(request.tc_ids),
        dashboard_url=f"/executions/{task.id}",
    )


@router.get("/{execution_id}", response_model=ExecutionStatus)
async def get_execution_status(execution_id: str):
    """
    获取执行状态
    
    实时查询执行进度
    """
    task_result = AsyncResult(execution_id)
    
    # 默认值
    status = task_result.status
    progress = 0.0
    meta = {
        "passed": 0, "failed": 0, "skipped": 0, "running": 0, 
        "pending": 0, "start_time": "", "elapsed_seconds": 0.0
    }
    
    if task_result.state == 'PROGRESS':
        meta.update(task_result.info or {})
        progress = meta.get("progress", 0.0)
    elif task_result.state == 'SUCCESS':
        progress = 100.0
        # 尝试从结果中获取更多详情
        if isinstance(task_result.result, dict):
             meta.update(task_result.result) # 结果可能包含统计信息
    elif task_result.state == 'FAILURE':
        progress = 0.0
        
    return ExecutionStatus(
        execution_id=execution_id,
        status=status,
        progress=progress,
        passed=meta.get("passed", 0),
        failed=meta.get("failed", 0),
        skipped=meta.get("skipped", 0),
        running=meta.get("running", 0),
        pending=meta.get("pending", 0),
        start_time=meta.get("start_time", ""),
        elapsed_seconds=meta.get("elapsed_seconds", 0.0)
    )


@router.get("/{execution_id}/result", response_model=ExecutionResult)
async def get_execution_result(execution_id: str):
    """
    获取执行结果
    
    返回完整的执行报告
    """
    # TODO: 从数据库查询结果
    raise HTTPException(status_code=404, detail=f"执行 {execution_id} 不存在")


@router.post("/{execution_id}/cancel", status_code=202)
async def cancel_execution_endpoint(execution_id: str):
    """
    取消执行
    
    终止正在运行的执行任务
    """
    # 调用 Celery 的终止方法
    AsyncResult(execution_id).revoke(terminate=True)
    
    # 也可以发送一个专门的取消任务来清理资源
    cancel_task.delay(execution_id)
    
    return {"message": f"取消请求已发送: {execution_id}"}


@router.get("", response_model=List[ExecutionStatus])
async def list_executions(
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """
    获取执行列表
    
    查询最近的执行记录
    """
    # TODO: 从数据库查询
    return []


@router.post("/ui/run")
async def run_ui_task(request: UiRunRequest):
    """
    运行 UI 自动化任务 (Right Pupil)
    """
    engine = RightPupilEngine()
    logs = await engine.run_task(request.prompt, request.url)
    return logs
