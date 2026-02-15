"""
执行管理端点

测试执行的启动、监控和结果查询
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from celery.result import AsyncResult
import uuid

from app.services.execution_service import ExecutionService
from app.tasks.execution_tasks import execute_test_cases, cancel_execution as cancel_task

router = APIRouter(tags=["Flow 3: Execution Dispatcher (任务调度)"])


# ===================== 数据模型 =====================

class UiRunRequest(BaseModel):
    """UI 任务请求"""
    prompt: str = Field(..., description="自然语言指令", example="打开百度首页并搜索 ChongMing")
    url: str = Field(..., description="目标 URL", example="https://www.baidu.com")


class ExecutionRequest(BaseModel):
    """执行请求"""
    tc_ids: List[str] = Field(..., description="测试用例 ID 列表", example=["TC-001", "TC-002"])
    mode: str = Field("normal", description="执行模式: normal (标准), debug (调试), fast (快速)", example="normal")
    parallel: bool = Field(True, description="是否开启并行执行")
    max_workers: int = Field(5, ge=1, le=20, description="最大并行 Worker 数量")
    env: Optional[str] = Field(None, description="目标运行环境 (如 dev, staging)", example="staging")


class ExecutionResponse(BaseModel):
    """执行响应"""
    execution_id: str = Field(..., description="执行活动 ID")
    status: str = Field(..., description="当前状态 (pending, running)")
    total_cases: int = Field(..., description="提交的用例总数")
    dashboard_url: str = Field(..., description="进度监控 Dashboard URL")


class ExecutionStatus(BaseModel):
    """执行状态详情"""
    execution_id: str = Field(..., description="执行 ID")
    status: str = Field(..., description="聚合状态 (passed, failed, running...)")
    progress: float = Field(..., description="进度百分比 (0.0 - 100.0)")
    passed: int = Field(0, description="通过数量")
    failed: int = Field(0, description="失败数量")
    skipped: int = Field(0, description="跳过数量")
    running: int = Field(0, description="运行中数量")
    pending: int = Field(0, description="等待中数量")
    start_time: str = Field("", description="开始时间 (ISO 8601)")
    elapsed_seconds: float = Field(0.0, description="已耗时 (秒)")


class ExecutionResult(BaseModel):
    """执行结果报告"""
    execution_id: str = Field(..., description="执行 ID")
    status: str = Field(..., description="最终状态")
    summary: dict = Field(..., description="统计摘要")
    cases: List[dict] = Field(..., description="用例执行详情列表")
    duration_seconds: float = Field(0.0, description="总耗时 (秒)")
    report_url: Optional[str] = Field(None, description="HTML 报告链接 (如有)")


# ===================== API 端点 =====================

@router.post(
    "", 
    response_model=ExecutionResponse, 
    status_code=202,
    summary="启动测试执行 (Start Execution)",
    description="""
    **Flow 3 核心接口**: 提交一批测试用例进行异步执行。
    
    - **调度逻辑**: 
        1. 解析 TC-IR (中间表示)。
        2. 根据 `parallel` 参数决定串行或并行。
        3. 自动分发任务到 Right Pupil (UI) 或 Left Pupil (API) 引擎。
    - **返回值**: `execution_id` 用于后续轮询状态。
    """
)
async def start_execution(
    request: ExecutionRequest,
    background_tasks: BackgroundTasks,
):
    """
    启动测试执行
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


@router.get(
    "/{execution_id}", 
    response_model=ExecutionStatus,
    summary="获取执行进度 (Get Status)",
    description="""
    **Flow 3 核心接口**: 实时查询测试执行的进度与状态。
    
    - **适用场景**: 前端进度条轮询。
    - **逻辑**: 优先查 Redis/Celery 状态，任务归档后查 Database。
    """
)
async def get_execution_status(execution_id: str):
    """
    获取执行状态
    """
    # 1. Try DB first (via service layer)
    db_dict = await ExecutionService.get_execution_status_dict(execution_id)
    if db_dict:
        return ExecutionStatus(**db_dict)

    # 2. Try Celery
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
            if "summary" in result_data and isinstance(result_data["summary"], dict):
                meta.update(result_data["summary"])
            meta.update(result_data)
            if "logs" in result_data and "passed" not in meta:
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


@router.get(
    "/{execution_id}/result", 
    response_model=ExecutionResult,
    summary="获取执行结果 (Get Result)",
    description="""
    **Flow 3 核心接口**: 获取完整的测试报告数据。
    
    - **包含**: 
        - 总体统计 (Pass/Fail Rate)
        - 每一个 Test Case 的详细步骤结果 (截图、错误日志、耗时)。
    """
)
async def get_execution_result(execution_id: str):
    """
    获取执行结果
    """
    # 1. Try DB (via service layer)
    db_dict = await ExecutionService.get_execution_result_dict(execution_id)
    if db_dict:
        return ExecutionResult(**db_dict)

    # 2. Try Celery (Fallback)
    task_result = AsyncResult(execution_id)
    
    if task_result.state == 'SUCCESS':
        data = task_result.result
        if not isinstance(data, dict):
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
            status="completed",
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


@router.post("/{execution_id}/cancel", status_code=202, summary="取消执行 (Cancel)")
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



@router.get("", response_model=List[ExecutionStatus], summary="执行历史列表 (List Executions)")
async def list_executions(
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """
    获取执行列表
    """
    dicts = await ExecutionService.list_executions_dicts(limit=limit)
    return [ExecutionStatus(**d) for d in dicts]


@router.post(
    "/ui/run", 
    response_model=List[dict], 
    tags=["Flow 2: Visual UI (右瞳引擎)"],
    summary="UI 任务 (Debug 同步)",
    description="""
    **Flow 2 调试接口**: 直接在当前进程运行 Playwright 任务（同步阻塞）。
    
    - **注意**: 仅用于开发调试，生产环境请使用 `/ui/run/async`。
    - **过程**:
        1. 启动 Playwright 浏览器。
        2. 执行 OmniParser 屏幕解析。
        3. Visual Grounding 定位元素。
        4. 执行操作。
    """
)
async def run_ui_task(request: UiRunRequest):
    """
    运行 UI 自动化任务 (Right Pupil) - 同步 Debug 模式
    """
    return await ExecutionService.run_ui_task(request.prompt, request.url)


class AdhocTaskResponse(BaseModel):
    task_id: str = Field(..., description="异步任务 ID")
    status: str = Field(..., description="任务初始化状态")
    dashboard_url: str = Field(..., description="任务进度链接")


@router.post(
    "/ui/run/async", 
    response_model=AdhocTaskResponse, 
    status_code=202,
    tags=["Flow 2: Visual UI (右瞳引擎)"],
    summary="UI 任务 (Async 异步)",
    description="""
    **Flow 2 生产接口**: 将 UI 自动化任务投递到 Worker 队列。
    
    - **优势**: 支持高并发，不阻塞 API 线程。
    - **输入**: Url 和 自然语言 Prompt (e.g. "点击登录按钮")。
    """
)
async def run_ui_task_async(request: UiRunRequest):
    """
    运行 UI 自动化任务 (Right Pupil) - 异步生产模式
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
