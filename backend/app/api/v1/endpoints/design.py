"""
Neural design endpoints.
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import fitz
from celery.result import AsyncResult
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_client import get_ai_manager
from app.core.database import get_db
from app.core.logging import logger
from app.core.config import settings
from app.models.environment import Environment
from app.services.left_pupil.rag_retriever import RagRetriever
from app.services.neural_design.analysis_tasks import (
    create_analysis_task,
    get_analysis_task,
    get_analysis_task_result,
)
from app.services.neural_design.models import DesignRequest, RefinedTestCase
from app.services.neural_design.service import DesignService
from app.tasks.design_tasks import analyze_requirement_task
from app.worker import celery


router = APIRouter(tags=["Flow 1: Neural Design"])


def get_design_service() -> DesignService:
    return DesignService(ai_manager=get_ai_manager(), retriever=RagRetriever())


class AnalyzeTaskCreated(BaseModel):
    task_id: str
    status: str
    stage: str
    progress: int
    status_url: str
    result_url: str
    created_at: str
    updated_at: str
    error: Optional[str] = None
    source: Optional[str] = None
    fallback_reason: Optional[str] = None
    timings: Dict[str, Any] = Field(default_factory=dict)


class AnalyzeTaskStatus(BaseModel):
    task_id: str
    status: str
    stage: str
    progress: int
    created_at: str
    updated_at: str
    status_url: str
    result_url: str
    error: Optional[str] = None
    source: Optional[str] = None
    fallback_reason: Optional[str] = None
    timings: Dict[str, Any] = Field(default_factory=dict)


class AnalyzeTaskResult(BaseModel):
    task_id: str
    status: str
    scenarios: List[Dict[str, Any]]
    error: Optional[str] = None
    source: Optional[str] = None
    fallback_reason: Optional[str] = None
    timings: Dict[str, Any] = Field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_task_urls(task_id: str) -> Dict[str, str]:
    return {
        "status_url": f"/api/v1/design/analyze/tasks/{task_id}",
        "result_url": f"/api/v1/design/analyze/tasks/{task_id}/result",
    }


def _make_analysis_task_id() -> str:
    return f"ANL_{uuid.uuid4().hex[:8].upper()}"


def _is_analysis_task_id(task_id: str) -> bool:
    return task_id.startswith("ANL_")


def _normalize_timings(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_active_celery_workers() -> bool:
    try:
        inspect = celery.control.inspect(timeout=0.5)
        ping_result = inspect.ping() if inspect else None
        return bool(ping_result)
    except Exception as exc:
        logger.warning(f"Failed to inspect Celery workers for analyze tasks: {exc}")
        return False


def _normalize_celery_task_status(task_id: str) -> Dict[str, Any]:
    task_result = AsyncResult(task_id, app=celery)
    state = task_result.state
    info = task_result.info if isinstance(task_result.info, dict) else {}
    urls = _build_task_urls(task_id)

    if state == "SUCCESS":
        result = task_result.result if isinstance(task_result.result, dict) else {}
        return {
            "task_id": task_id,
            "status": result.get("status", "completed"),
            "stage": result.get("stage", "completed"),
            "progress": int(result.get("progress", 100)),
            "created_at": result.get("created_at", ""),
            "updated_at": result.get("updated_at", ""),
            "error": result.get("error"),
            "source": result.get("source"),
            "fallback_reason": result.get("fallback_reason"),
            "timings": _normalize_timings(result.get("timings")),
            **urls,
        }

    if state in {"PROGRESS", "STARTED"}:
        return {
            "task_id": task_id,
            "status": "running",
            "stage": info.get("stage", "starting" if state == "STARTED" else "queued"),
            "progress": int(info.get("progress", 5 if state == "STARTED" else 0)),
            "created_at": info.get("created_at", ""),
            "updated_at": info.get("updated_at", info.get("created_at", "")),
            "error": info.get("error"),
            "source": info.get("source"),
            "fallback_reason": info.get("fallback_reason"),
            "timings": _normalize_timings(info.get("timings")),
            **urls,
        }

    if state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "stage": "failed",
            "progress": 100,
            "created_at": info.get("created_at", ""),
            "updated_at": info.get("updated_at", info.get("created_at", "")),
            "error": str(task_result.result or task_result.info or "Analyze task failed"),
            "source": info.get("source"),
            "fallback_reason": info.get("fallback_reason"),
            "timings": _normalize_timings(info.get("timings")),
            **urls,
        }

    return {
        "task_id": task_id,
        "status": "pending",
        "stage": "queued",
        "progress": 0,
        "created_at": "",
        "updated_at": "",
        "error": None,
        "source": None,
        "fallback_reason": None,
        "timings": {},
        **urls,
    }


def _get_celery_task_result_payload(task_id: str) -> Dict[str, Any]:
    task_result = AsyncResult(task_id, app=celery)
    state = task_result.state
    info = task_result.info if isinstance(task_result.info, dict) else {}

    if state == "SUCCESS":
        result = task_result.result if isinstance(task_result.result, dict) else {}
        return {
            "task_id": task_id,
            "status": result.get("status", "completed"),
            "scenarios": result.get("scenarios", []),
            "error": result.get("error"),
            "source": result.get("source"),
            "fallback_reason": result.get("fallback_reason"),
            "timings": _normalize_timings(result.get("timings")),
        }

    if state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "scenarios": [],
            "error": str(task_result.result or task_result.info or "Analyze task failed"),
            "source": info.get("source"),
            "fallback_reason": info.get("fallback_reason"),
            "timings": _normalize_timings(info.get("timings")),
        }

    return {
        "task_id": task_id,
        "status": "running" if state in {"PROGRESS", "STARTED"} else "pending",
        "scenarios": [],
        "error": None,
        "source": info.get("source"),
        "fallback_reason": info.get("fallback_reason"),
        "timings": _normalize_timings(info.get("timings")),
    }


async def _apply_default_environment(request: DesignRequest, db: AsyncSession) -> DesignRequest:
    env_stmt = select(Environment).where(
        Environment.is_default == True,
        Environment.is_active == True,
    )
    env_result = await db.execute(env_stmt)
    default_env = env_result.scalar_one_or_none()

    if not default_env:
        fallback_stmt = select(Environment).where(Environment.is_active == True).limit(1)
        fallback_result = await db.execute(fallback_stmt)
        default_env = fallback_result.scalar_one_or_none()

    env_context = ""
    if default_env and getattr(default_env, "base_url", None):
        base_url = default_env.base_url
        if not getattr(request, "target_url", None):
            request.target_url = base_url
        env_context = (
            "\n\n[System Candidate Test Environment]\n"
            f"If the requirement does not specify a target URL or domain, you may use this base URL: {base_url}\n"
            "If the requirement or context explicitly specifies a target URL/domain, always prioritize that value.\n"
            "For API steps, generated paths must be absolute request URLs rather than relative-only paths."
        )

    request.context = (request.context or "") + env_context
    return request


@router.post(
    "/upload",
    summary="Parse uploaded document",
    description="Support .md, .pdf and .json document text extraction.",
)
async def upload_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        filename = file.filename.lower()

        extracted_text = ""
        file_type = "unknown"

        if filename.endswith(".md") or filename.endswith(".txt"):
            extracted_text = content.decode("utf-8")
            file_type = "markdown"
        elif filename.endswith(".pdf"):
            doc = fitz.open(stream=content, filetype="pdf")
            for page in doc:
                extracted_text += page.get_text() + "\n"
            doc.close()
            file_type = "pdf"
        elif filename.endswith(".json"):
            json_data = json.loads(content.decode("utf-8"))
            extracted_text = json.dumps(json_data, ensure_ascii=False, indent=2)
            file_type = "json"
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Please upload .md, .pdf, or .json",
            )

        return {
            "filename": file.filename,
            "file_type": file_type,
            "extracted_text": extracted_text.strip(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to parse uploaded file: {exc}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"File parsing failed: {exc}")


@router.post(
    "/analyze/async",
    response_model=AnalyzeTaskCreated,
    status_code=202,
    summary="Analyze PRD asynchronously",
)
async def analyze_prd_async(
    request: DesignRequest,
    db: AsyncSession = Depends(get_db),
):
    request = await _apply_default_environment(request, db)

    if _has_active_celery_workers():
        task_id = _make_analysis_task_id()
        created_at = _now_iso()
        analyze_requirement_task.apply_async(
            kwargs={
                "request_payload": request.model_dump(),
                "submitted_at": created_at,
            },
            task_id=task_id,
        )
        task = {
            "task_id": task_id,
            "status": "pending",
            "stage": "queued",
            "progress": 0,
            "created_at": created_at,
            "updated_at": created_at,
            "error": None,
            "source": None,
            "fallback_reason": None,
            "timings": {},
            **_build_task_urls(task_id),
        }
    else:
        async def _runner(
            enriched_request: DesignRequest,
            progress_callback=None,
        ) -> List[Dict[str, Any]]:
            service = get_design_service()
            return await service.analyze_requirement(
                enriched_request,
                progress_callback=progress_callback,
            )

        task = create_analysis_task(request, _runner)

    logger.info(
        f"Design Analysis Async Task [CREATED]: task_id={task['task_id']}, "
        f"project={request.project_id}, type={request.target_type}"
    )
    return AnalyzeTaskCreated(**task)


@router.get(
    "/analyze/tasks/{task_id}",
    response_model=AnalyzeTaskStatus,
    summary="Get analyze task status",
)
async def get_analyze_task_status(task_id: str):
    task = get_analysis_task(task_id)
    if task:
        return AnalyzeTaskStatus(**task)

    if not _is_analysis_task_id(task_id):
        raise HTTPException(status_code=404, detail="Analyze task not found")

    return AnalyzeTaskStatus(**_normalize_celery_task_status(task_id))


@router.get(
    "/analyze/tasks/{task_id}/result",
    response_model=AnalyzeTaskResult,
    summary="Get analyze task result",
)
async def get_analyze_task_result(task_id: str):
    task = get_analysis_task_result(task_id)
    if task:
        if task["status"] in {"pending", "running"}:
            return JSONResponse(
                status_code=202,
                content={
                    "task_id": task_id,
                    "status": task["status"],
                    "scenarios": [],
                    "error": None,
                    "source": task.get("source"),
                    "fallback_reason": task.get("fallback_reason"),
                    "timings": task.get("timings") or {},
                },
            )

        if task["status"] == "failed":
            return JSONResponse(
                status_code=500,
                content={
                    "task_id": task_id,
                    "status": "failed",
                    "scenarios": [],
                    "error": task.get("error"),
                    "source": task.get("source"),
                    "fallback_reason": task.get("fallback_reason"),
                    "timings": task.get("timings") or {},
                },
            )

        return AnalyzeTaskResult(
            task_id=task_id,
            status=task["status"],
            scenarios=(task.get("result") or {}).get("scenarios", []),
            error=task.get("error"),
            source=task.get("source"),
            fallback_reason=task.get("fallback_reason"),
            timings=task.get("timings") or {},
        )

    if not _is_analysis_task_id(task_id):
        raise HTTPException(status_code=404, detail="Analyze task not found")

    payload = _get_celery_task_result_payload(task_id)
    if payload["status"] in {"pending", "running"}:
        return JSONResponse(status_code=202, content=payload)
    if payload["status"] == "failed":
        return JSONResponse(status_code=500, content=payload)
    return AnalyzeTaskResult(**payload)


@router.post(
    "/analyze",
    response_model=List[Dict[str, Any]],
    summary="Analyze PRD",
)
async def analyze_prd(
    request: DesignRequest,
    service: DesignService = Depends(get_design_service),
    db: AsyncSession = Depends(get_db),
):
    try:
        request = await _apply_default_environment(request, db)

        logger.info(
            f"Design Analysis Request [START]: Project={request.project_id}, "
            f"Type={request.target_type}, Model={settings.MODEL_NEURAL_SCENARIO}"
        )
        logger.info("Preparing requirement analysis via DesignService...")
        scenarios = await asyncio.wait_for(
            service.analyze_requirement(request),
            timeout=300.0,
        )

        logger.info(f"Design Analysis Request [SUCCESS]: Generated {len(scenarios)} scenarios.")
        return scenarios
    except asyncio.CancelledError:
        logger.warning("Design analysis request cancelled by client.")
        print("CRITICAL WARNING: Request cancelled by client")
        raise
    except asyncio.TimeoutError:
        error_detail = "Design Analysis Timed Out (300s limit reached)"
        logger.error(error_detail)
        print(f"CRITICAL ERROR: {error_detail}")
        raise HTTPException(status_code=504, detail=error_detail)
    except Exception as exc:
        error_detail = f"Requirement analysis failed: {exc}"
        logger.error(f"Design Analysis Failed: {exc}")
        logger.error(traceback.format_exc())
        print(f"CRITICAL ERROR: {error_detail}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": error_detail, "type": type(exc).__name__},
        )


@router.post(
    "/generate",
    response_model=RefinedTestCase,
    summary="Generate refined test case",
)
async def generate_test_case_endpoint(
    scenario: Dict[str, Any] = Body(..., description="Scenario definition object"),
    project_id: str = Body(..., description="Project ID context"),
    service: DesignService = Depends(get_design_service),
):
    try:
        return await service.generate_test_case(scenario, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Test case generation failed: {exc}")
