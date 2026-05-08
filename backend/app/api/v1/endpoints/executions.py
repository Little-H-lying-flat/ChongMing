"""
执行管理端点

测试执行的启动、监控和结果查询
"""

from pathlib import Path
import re
from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from celery.result import AsyncResult
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.environment_manager import EnvironmentManager
from app.services.execution_service import ExecutionService
from app.tasks.execution_tasks import execute_test_cases, cancel_execution as cancel_task
from app.core.logging import logger
from app.worker import celery

router = APIRouter(tags=["Flow 3: Execution Dispatcher (任务调度)"])
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_VARIABLE_REF_PATTERN = re.compile(r"\$\{([^}]+)\}|\{\{([^}]+)\}\}")


def _has_active_celery_workers() -> bool:
    try:
        inspect = celery.control.inspect(timeout=0.5)
        ping_result = inspect.ping() if inspect else None
        return bool(ping_result)
    except Exception as exc:
        logger.warning(f"Failed to inspect Celery workers, falling back to local execution: {exc}")
        return False


def _run_execution_locally(
    execution_id: str,
    tc_ids: List[str],
    config: dict,
    dynamic_payload: Optional[List[dict]] = None,
) -> None:
    logger.warning(
        f"No active Celery worker detected. Running execution {execution_id} in local background mode."
    )
    execute_test_cases.run(
        execution_id=execution_id,
        tc_ids=tc_ids,
        config=config,
        dynamic_payload=dynamic_payload,
    )


def _collect_required_variables(value: Any, bucket: set[str]) -> None:
    if isinstance(value, str):
        for match in _VARIABLE_REF_PATTERN.finditer(value):
            variable_name = (match.group(1) or match.group(2) or "").strip()
            if variable_name:
                bucket.add(variable_name)
        return

    if isinstance(value, dict):
        for nested in value.values():
            _collect_required_variables(nested, bucket)
        return

    if isinstance(value, list):
        for item in value:
            _collect_required_variables(item, bucket)


def _extract_payload_required_variables(dynamic_payload: Optional[List[dict]]) -> List[str]:
    required_variables: set[str] = set()
    for case in dynamic_payload or []:
        declared = case.get("required_variables")
        if isinstance(declared, list):
            for variable_name in declared:
                if isinstance(variable_name, str) and variable_name.strip():
                    required_variables.add(variable_name.strip())
        _collect_required_variables(case.get("steps", []), required_variables)
    return sorted(required_variables)


async def _load_execution_environment_context(
    env_id: Optional[str],
    db: AsyncSession,
) -> tuple[dict, Optional[str], Optional[str]]:
    manager = EnvironmentManager(db)
    env = await manager.get(env_id) if env_id else await manager.get_default()
    if not env:
        return {}, None, None

    context: dict[str, Any] = {}
    for key, var in (env.variables or {}).items():
        value = var.get("value", "")
        if var.get("encrypted"):
            value = manager._decrypt(value)
        context[key] = value
    context["base_url"] = env.base_url
    context["env_name"] = env.name
    return context, env.id, env.name


# ===================== 数据模型 =====================

class UiRunRequest(BaseModel):
    """UI 任务请求"""
    prompt: str = Field(..., description="自然语言指令", json_schema_extra={"example": "打开百度首页并搜索 ChongMing"})
    url: str = Field(..., description="目标 URL", json_schema_extra={"example": "https://www.baidu.com"})


class ExecutionRequest(BaseModel):
    """执行请求"""
    tc_ids: List[str] = Field(..., description="测试用例 ID 列表", json_schema_extra={"example": ["TC-001", "TC-002"]})
    mode: str = Field("normal", description="执行模式: normal (标准), debug (调试), fast (快速)", json_schema_extra={"example": "normal"})
    parallel: bool = Field(True, description="是否开启并行执行")
    max_workers: int = Field(5, ge=1, le=20, description="最大并行 Worker 数量")
    env: Optional[str] = Field(None, description="目标运行环境 (如 dev, staging)", json_schema_extra={"example": "staging"})
    dynamic_payload: Optional[List[dict]] = Field(None, description="动态测试用例 Payload (用于临时运行)")


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
    """执行结果详情"""
    execution_id: str = Field(..., description="执行 ID")
    status: str = Field(..., description="状态")
    summary: dict = Field(..., description="统计摘要")
    cases: List[dict] = Field([], description="用例结果列表")
    duration_seconds: float = Field(0.0, description="耗时 (秒)")
    report_url: Optional[str] = Field(None, description="报告链接")


class DashboardStats(BaseModel):
    """大盘统计数据"""
    active: int = Field(..., description="运行中或等待中的任务数")
    success_rate: float = Field(..., description="全局成功率")
    avg_duration: float = Field(..., description="平均耗时 (秒)")
    total: int = Field(..., description="总执行次数")


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
    - **支持 Dynamic Payload**: 可以通过 `dynamic_payload` 直接传递临时测试用例 (Neural Design)。
    - **返回值**: `execution_id` 用于后续轮询状态。
    """
)
async def start_execution(
    request: ExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    启动测试执行
    """
    # 1. Generate Execution ID
    execution_id = f"EXEC_{uuid.uuid4().hex[:8].upper()}"
    
    # 2. Config Dict
    config = {
        "mode": request.mode,
        "parallel": request.parallel,
        "max_workers": request.max_workers,
        "env": request.env
    }

    required_variables = _extract_payload_required_variables(request.dynamic_payload)
    if required_variables:
        available_context, resolved_env_id, resolved_env_name = await _load_execution_environment_context(
            request.env,
            db,
        )
        missing_variables = sorted(
            variable_name for variable_name in required_variables if variable_name not in available_context
        )
        if missing_variables:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "missing_execution_variables",
                    "message": "Missing required execution variables.",
                    "missing_variables": missing_variables,
                    "required_variables": required_variables,
                    "env_id": resolved_env_id,
                    "env_name": resolved_env_name,
                },
            )
    
    # 3. Synchronous DB Creation (Fixes Race Condition)
    await ExecutionService.create_execution(execution_id, request.tc_ids, config)
    
    # 4. Dispatch Task with existing ID
    if _has_active_celery_workers():
        execute_test_cases.delay(  # type: ignore[misc]  # Celery task
            execution_id=execution_id,
            tc_ids=request.tc_ids,
            config=config,
            dynamic_payload=request.dynamic_payload
        )
    else:
        background_tasks.add_task(
            _run_execution_locally,
            execution_id,
            request.tc_ids,
            config,
            request.dynamic_payload,
        )
    
    return ExecutionResponse(
        execution_id=execution_id,
        status="pending",
        total_cases=len(request.tc_ids),
        dashboard_url=f"/executions/{execution_id}",
    )


@router.get("/stats", response_model=DashboardStats, summary="获取大盘高级指标 (Stats)")
async def get_execution_stats():
    """获取调度大盘全局指标"""
    return await ExecutionService.get_execution_stats()


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
        summary=task_result.info if isinstance(task_result.info, dict) else {},
        cases=[],
        duration_seconds=0.0,
        report_url=None
    )


@router.get(
    "/{execution_id}/steps",
    summary="获取执行步骤详情 (Get Steps)",
    description="""
    **Flow 3 Debug 接口**: 获取指定执行任务的所有详细步骤结果。
    
    - **返回**: 包含每个 Test Case 的详细执行日志、截图路径、API 响应状态码等。
    - **用途**: 前端 Drawer 展示“极客风”调试信息。
    """
)
async def get_execution_steps(execution_id: str):
    """
    获取执行步骤详情
    """
    return await ExecutionService.get_execution_result_dict(execution_id)


def _ensure_safe_filename(name: str, field_name: str) -> str:
    if not name or not _SAFE_FILENAME_RE.fullmatch(name):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return name


def _resolve_safe_screenshot_path(execution_id: str, filename: str) -> Path:
    safe_execution_id = _ensure_safe_filename(execution_id, "execution_id")
    safe_filename = _ensure_safe_filename(filename, "filename")

    base_dir = (Path("data") / "screenshots").resolve()
    target = (base_dir / safe_execution_id / safe_filename).resolve()
    if not str(target).startswith(str(base_dir)):
        raise HTTPException(status_code=400, detail="Invalid screenshot path")
    return target


@router.get(
    "/{execution_id}/screenshot/{case_idx}/{step_idx}/{img_type}",
    summary="获取步骤截图 (Get Screenshot)",
    description="优先从本地磁盘读取截图，若为历史遗留数据则从 DB 中读取 base64。",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_step_screenshot(
    execution_id: str,
    case_idx: int,
    step_idx: int,
    img_type: str,  # "before" or "after"
    tc_id: Optional[str] = None
):
    """
    按需获取截图二进制数据或文件
    """
    from fastapi.responses import Response, FileResponse
    import base64

    if img_type not in ("before", "after"):
        raise HTTPException(status_code=400, detail="img_type must be 'before' or 'after'")

    # 1. 尝试从本地磁盘读取 (优化后的架构)
    if tc_id:
        safe_tc_id = _ensure_safe_filename(tc_id, "tc_id")
        filename = f"{safe_tc_id}_{step_idx}_{img_type}.png"
        filepath = _resolve_safe_screenshot_path(execution_id, filename)
        if filepath.exists():
            return FileResponse(filepath, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

    # 2. 从 DB 获取原始数据（兼容历史执行数据）
    result = await ExecutionService.get_execution_result_dict(
        execution_id, strip_screenshots=False
    )
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")

    cases = result.get("cases", [])
    if case_idx >= len(cases):
        raise HTTPException(status_code=404, detail="Case index out of range")

    steps = cases[case_idx].get("steps", [])
    if step_idx >= len(steps):
        raise HTTPException(status_code=404, detail="Step index out of range")

    details = steps[step_idx].get("details", {})
    field = f"screenshot_{img_type}"
    b64_data = details.get(field)

    if not b64_data:
        raise HTTPException(status_code=404, detail="Screenshot not available")

    # If the marker LOCAL was accidentally kept in DB
    if b64_data.startswith("LOCAL:"):
        filename = b64_data.replace("LOCAL:", "", 1)
        filepath = _resolve_safe_screenshot_path(execution_id, filename)
        if filepath.exists():
            return FileResponse(filepath, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
        else:
            raise HTTPException(status_code=404, detail="Local screenshot file missing")

    # Strip data URI prefix if present
    if b64_data.startswith("data:image"):
        b64_data = b64_data.split(",", 1)[-1]

    try:
        img_bytes = base64.b64decode(b64_data)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decode screenshot")

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},  # Cache 24h
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
    cancel_task.delay(execution_id)  # type: ignore[misc]  # Celery task
    
    return {"message": f"取消请求已发送: {execution_id}"}



class PaginatedExecutions(BaseModel):
    total: int = Field(..., description="总记录数")
    items: List[ExecutionStatus] = Field(..., description="当页数据")

@router.get("", response_model=PaginatedExecutions, summary="执行历史列表 (List Executions)")
async def list_executions(
    status: Optional[str] = Query(None, description="状态过滤"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """
    获取带分页的执行列表
    """
    data = await ExecutionService.list_executions_dicts(skip=skip, limit=limit)
    return {"total": data["total"], "items": [ExecutionStatus(**d) for d in data["items"]]}


@router.delete(
    "/{execution_id}",
    summary="删除执行记录 (Delete Execution)",
    description="删除指定的执行历史记录以及相关联的测试步骤和本地截图数据。"
)
async def delete_execution(execution_id: str):
    """
    删除执行记录
    """
    success = await ExecutionService.delete_execution(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail="Execution not found or could not be deleted")
    return {"message": "Execution deleted successfully", "execution_id": execution_id}


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
        
        task = execute_adhoc_task.delay(request.prompt, request.url)  # type: ignore  # Celery task .delay()
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
