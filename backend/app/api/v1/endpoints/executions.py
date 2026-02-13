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
        result_data = task_result.result
        if isinstance(result_data, dict):
            # 1. 尝试提取 Task 中的 summary 字段 (execute_test_cases)
            if "summary" in result_data and isinstance(result_data["summary"], dict):
                meta.update(result_data["summary"])
            
            # 2. 尝试提取直接字段 (兼容旧格式或部分更新)
            meta.update(result_data)
            
            # 3. 针对 Ad-hoc 任务 (execute_adhoc_task) 的特殊处理
            # 它的结果是 {"status": "completed", "logs": [...]}
            if "logs" in result_data and "passed" not in meta:
                # Ad-hoc 任务成功由于没有 passed/failed 计数，我们手动设置为 1
                meta["passed"] = 1
                meta["total"] = 1

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
    task_result = AsyncResult(execution_id)
    
    if task_result.state == 'SUCCESS':
        data = task_result.result
        if not isinstance(data, dict):
             # 可能是简单的返回值
             return ExecutionResult(
                execution_id=execution_id,
                status="completed",
                summary={"result": str(data)},
                cases=[],
                duration_seconds=0.0,
                report_url=None
            )
             
        return ExecutionResult(
            execution_id=data.get("execution_id", execution_id),
            status="completed", # Force completed if success
            summary=data.get("summary", {"total": 0, "passed": 0, "failed": 0, "error": 0}),
            cases=data.get("results", []) if isinstance(data.get("results"), list) else [],
            duration_seconds=data.get("duration_ms", 0) / 1000.0 if "duration_ms" in data else 0.0,
            report_url=None
        )
        
    elif task_result.state == 'FAILURE':
        return ExecutionResult(
            execution_id=execution_id,
            status="failed",
            summary={"error": 1},
            cases=[],
            duration_seconds=0.0,
            report_url=None
        )
        
    # Running / Pending
    return ExecutionResult(
        execution_id=execution_id,
        status=task_result.state.lower(),
        summary=task_result.info or {} if isinstance(task_result.info, dict) else {},
        cases=[],
        duration_seconds=0.0,
        report_url=None
    )


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
    # TODO: 从数据库查询 real history
    # Return empty list to prevent frontend crash
    return []


@router.post("/ui/run", response_model=List[dict])
async def run_ui_task(request: UiRunRequest):
    """
    运行 UI 自动化任务 (Right Pupil) - 同步 Debug 模式
    """
    engine = RightPupilEngine()
    logs = await engine.run_task(request.prompt, request.url)
    return logs


class AdhocTaskResponse(BaseModel):
    task_id: str
    status: str
    dashboard_url: str


@router.post("/ui/run/async", response_model=AdhocTaskResponse, status_code=202)
async def run_ui_task_async(request: UiRunRequest):
    """
    运行 UI 自动化任务 (Right Pupil) - 异步生产模式
    
    推荐用于高并发场景
    """
    try:
        from app.tasks.execution_tasks import execute_adhoc_task
        print("Imported execute_adhoc_task")
        
        task = execute_adhoc_task.delay(request.prompt, request.url)
        print(f"Task dispatched: {task.id}")
        
        return {
            "task_id": task.id,
            "status": "pending",
            "dashboard_url": f"/tasks/{task.id}/progress"
        }
    except Exception as e:
        import traceback
        with open("trace.log", "w") as f:
            f.write(traceback.format_exc())
        traceback.print_exc()
        raise e
