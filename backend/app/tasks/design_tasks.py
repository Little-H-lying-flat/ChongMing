"""
Celery tasks for neural design workflows.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import shared_task
from loguru import logger

from app.core.ai_client import get_ai_manager
from app.services.left_pupil.rag_retriever import RagRetriever
from app.services.neural_design.models import DesignRequest
from app.services.neural_design.service import DesignService
from app.tasks.base import DesignGenTask


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_meta(
    stage: str,
    progress: int,
    created_at: str,
    *,
    source: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    timings: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": "running" if stage != "failed" else "failed",
        "stage": stage,
        "progress": progress,
        "created_at": created_at,
        "updated_at": _now_iso(),
        "source": source,
        "fallback_reason": fallback_reason,
        "timings": timings or {},
        "error": error,
    }


@shared_task(
    bind=True,
    base=DesignGenTask,
    name="app.tasks.design_tasks.analyze_requirement_task",
)
def analyze_requirement_task(
    self,
    request_payload: Dict[str, Any],
    submitted_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run requirement analysis through Celery and persist task state in the
    configured Celery result backend.
    """
    created_at = submitted_at or _now_iso()
    self.update_state(
        state="PROGRESS",
        meta=_build_meta("starting", 5, created_at),
    )

    request = DesignRequest.model_validate(request_payload)
    service = DesignService(
        ai_manager=get_ai_manager(),
        retriever=RagRetriever(),
    )

    last_details: Dict[str, Any] = {
        "source": None,
        "fallback_reason": None,
        "timings": {},
    }

    def _progress_callback(stage: str, progress: int, extra: Optional[Dict[str, Any]] = None) -> None:
        payload = dict(extra or {})
        if "source" in payload:
            last_details["source"] = payload.get("source")
        if "fallback_reason" in payload:
            last_details["fallback_reason"] = payload.get("fallback_reason")
        if "timings" in payload and isinstance(payload.get("timings"), dict):
            last_details["timings"] = payload.get("timings") or {}

        self.update_state(
            state="PROGRESS",
            meta=_build_meta(
                stage,
                progress,
                created_at,
                source=last_details.get("source"),
                fallback_reason=last_details.get("fallback_reason"),
                timings=last_details.get("timings"),
            ),
        )

    try:
        scenarios = asyncio.run(
            service.analyze_requirement(
                request,
                progress_callback=_progress_callback,
            )
        )
    except Exception as exc:
        logger.exception(
            f"Analyze requirement task failed. task_id={self.request.id} "
            f"project={request.project_id}"
        )
        self.update_state(
            state="FAILURE",
            meta=_build_meta(
                "failed",
                100,
                created_at,
                source=last_details.get("source"),
                fallback_reason=last_details.get("fallback_reason"),
                timings=last_details.get("timings"),
                error=str(exc),
            ),
        )
        raise

    result = {
        "status": "completed",
        "stage": "completed",
        "progress": 100,
        "created_at": created_at,
        "updated_at": _now_iso(),
        "scenarios": scenarios,
        "source": last_details.get("source"),
        "fallback_reason": last_details.get("fallback_reason"),
        "timings": last_details.get("timings") or {},
        "error": None,
    }
    logger.info(
        f"Analyze requirement task completed. task_id={self.request.id} "
        f"project={request.project_id} scenarios={len(scenarios)}"
    )
    return result


@shared_task(bind=True, name="app.tasks.generate_test_cases")
def generate_test_cases(
    self,
    intent: str,
    constraints: Optional[dict] = None,
    context: Optional[list] = None,
    max_cases: int = 10,
) -> Dict[str, Any]:
    logger.info(f"Placeholder generate_test_cases task called. intent={intent}")
    self.update_state(
        state="PROGRESS",
        meta={
            "stage": "parsing_intent",
            "progress": 10,
            "message": "Parsing intent",
        },
    )
    return {
        "status": "completed",
        "drafts": [],
        "intent": intent,
        "constraints": constraints or {},
        "context": context or [],
        "max_cases": max_cases,
    }


@shared_task(name="app.tasks.confirm_drafts")
def confirm_drafts(draft_ids: list, modifications: Optional[dict] = None) -> Dict[str, Any]:
    logger.info(f"Placeholder confirm_drafts task called. draft_count={len(draft_ids)}")
    return {
        "confirmed_count": len(draft_ids),
        "modifications": modifications or {},
    }
