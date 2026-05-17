"""Midscene execution adapter."""

import time
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.execution import ExecutionResult, StepResult, TCIR


class MidsceneAdapter:
    async def execute(self, tc_ir: TCIR, initial_context: dict[str, Any] | None = None) -> ExecutionResult:
        start_time = time.time()
        payload = {
            "case": {
                "id": tc_ir.id,
                "name": tc_ir.name,
                "description": tc_ir.description,
                "mode": getattr(tc_ir.mode, "value", tc_ir.mode),
                "steps": tc_ir.steps,
            },
            "context": initial_context or {},
        }

        async with httpx.AsyncClient(timeout=settings.MIDSCENE_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{settings.MIDSCENE_RUNNER_URL.rstrip('/')}/run", json=payload)
            response.raise_for_status()
            data = response.json()

        raw_steps = data.get("steps", [])
        step_results = [self._to_step_result(index, step) for index, step in enumerate(raw_steps)]
        success = bool(data.get("success", all(step.success for step in step_results)))
        status = str(data.get("status") or ("passed" if success else "failed"))
        duration_ms = float(data.get("duration_ms") or ((time.time() - start_time) * 1000))

        return ExecutionResult(
            tc_id=tc_ir.id,
            success=success,
            status=status,
            step_results=step_results,
            total_duration_ms=duration_ms,
            trace_id=str(data.get("trace_id") or f"TRACE_{uuid.uuid4().hex[:8].upper()}"),
            error=data.get("error"),
            variable_trace=data.get("variable_trace", []),
        )

    @staticmethod
    def _to_step_result(index: int, step: dict[str, Any]) -> StepResult:
        details = step.get("details") if isinstance(step.get("details"), dict) else {}
        screenshot = step.get("screenshot") or details.get("screenshot_after")
        return StepResult(
            step_index=int(step.get("step_index", index)),
            success=bool(step.get("success", step.get("status") == "passed")),
            duration_ms=float(step.get("duration_ms", 0.0)),
            screenshot=screenshot,
            error=step.get("error"),
            details=details,
            description=step.get("description") or details.get("step_name"),
        )
