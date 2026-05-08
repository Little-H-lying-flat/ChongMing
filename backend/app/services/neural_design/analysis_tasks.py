import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from app.services.neural_design.models import DesignRequest


_TASK_TTL_SECONDS = 3600
_MAX_TASKS = 128
_tasks: Dict[str, Dict[str, Any]] = {}
AnalysisRunner = Callable[
    [DesignRequest, Optional[Callable[[str, int, Optional[Dict[str, Any]]], None]]],
    Awaitable[list[dict[str, Any]]],
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_request(request: DesignRequest) -> Dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump()
    return request.dict()


def _prune_tasks() -> None:
    now = time.time()
    expired = []
    for task_id, task in _tasks.items():
        updated_at = task.get("_updated_ts", task.get("_created_ts", now))
        is_terminal = task.get("status") in {"completed", "failed", "cancelled"}
        if is_terminal and (now - updated_at) > _TASK_TTL_SECONDS:
            expired.append(task_id)

    for task_id in expired:
        _tasks.pop(task_id, None)

    if len(_tasks) <= _MAX_TASKS:
        return

    ordered = sorted(
        _tasks.items(),
        key=lambda item: item[1].get("_created_ts", 0),
    )
    for task_id, _ in ordered[: max(0, len(_tasks) - _MAX_TASKS)]:
        _tasks.pop(task_id, None)


def _public_task(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "stage": task.get("stage", ""),
        "progress": task.get("progress", 0),
        "created_at": task.get("created_at", ""),
        "updated_at": task.get("updated_at", ""),
        "error": task.get("error"),
        "result_url": task.get("result_url"),
        "status_url": task.get("status_url"),
        "source": task.get("source"),
        "fallback_reason": task.get("fallback_reason"),
        "timings": task.get("timings") or {},
    }


def _set_task_state(task_id: str, **updates: Any) -> None:
    task = _tasks.get(task_id)
    if not task:
        return

    task.update(updates)
    task["updated_at"] = _now_iso()
    task["_updated_ts"] = time.time()


async def _run_task(
    task_id: str,
    request: DesignRequest,
    runner: AnalysisRunner,
) -> None:
    def _progress_callback(stage: str, progress: int, extra: Optional[Dict[str, Any]] = None) -> None:
        payload = dict(extra or {})
        _set_task_state(
            task_id,
            status="running",
            stage=stage,
            progress=progress,
            source=payload.get("source"),
            fallback_reason=payload.get("fallback_reason"),
            timings=payload.get("timings"),
        )

    _set_task_state(task_id, status="running", stage="starting", progress=5, error=None)

    try:
        scenarios = await runner(request, _progress_callback)
        _set_task_state(
            task_id,
            status="completed",
            stage="completed",
            progress=100,
            result={"scenarios": scenarios},
        )
    except Exception as exc:
        _set_task_state(
            task_id,
            status="failed",
            stage="failed",
            progress=100,
            error=str(exc),
        )


def create_analysis_task(
    request: DesignRequest,
    runner: AnalysisRunner,
) -> Dict[str, Any]:
    _prune_tasks()
    task_id = f"ANL_{uuid.uuid4().hex[:8].upper()}"
    created_at = _now_iso()

    task = {
        "task_id": task_id,
        "status": "pending",
        "stage": "queued",
        "progress": 0,
        "created_at": created_at,
        "updated_at": created_at,
        "_created_ts": time.time(),
        "_updated_ts": time.time(),
        "request": json.loads(json.dumps(_serialize_request(request), ensure_ascii=False)),
        "result": None,
        "error": None,
        "status_url": f"/api/v1/design/analyze/tasks/{task_id}",
        "result_url": f"/api/v1/design/analyze/tasks/{task_id}/result",
    }
    _tasks[task_id] = task
    task["future"] = asyncio.create_task(_run_task(task_id, request, runner))
    return _public_task(task)


def get_analysis_task(task_id: str) -> Optional[Dict[str, Any]]:
    _prune_tasks()
    task = _tasks.get(task_id)
    if not task:
        return None
    return _public_task(task)


def get_analysis_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    _prune_tasks()
    return _tasks.get(task_id)
