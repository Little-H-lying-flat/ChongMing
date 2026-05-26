from __future__ import annotations

import pytest

from app.models.execution import Execution, ExecutionStatus

from .test_scan_campaigns_phase3_execution import CONFIRMATION, _campaign_payload, _prepare_promoted_assets


@pytest.mark.asyncio
async def test_phase4_execution_summary_empty_before_execution(client) -> None:
    created = await client.post("/api/v1/scan-campaigns", json=_campaign_payload())
    assert created.status_code == 201
    campaign_id = created.json()["id"]

    generated = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/generate-plan",
        json={"notes": "Phase 4 empty summary"},
    )
    assert generated.status_code == 200
    plan_id = generated.json()["plan_id"]

    response = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/execution-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_executions"] == 0
    assert body["latest_execution_id"] is None
    assert body["executions"] == []
    assert body["result_breakdown"]["api"] == {"total": 0, "passed": 0, "failed": 0}


@pytest.mark.asyncio
async def test_phase4_execution_summary_lists_smart_scan_executions(client, db_session, monkeypatch) -> None:
    from app.api.v1.endpoints import executions as execution_endpoint

    monkeypatch.setattr(execution_endpoint, "_has_active_celery_workers", lambda: True)
    monkeypatch.setattr(execution_endpoint.execute_test_cases, "apply_async", lambda **kwargs: None)

    campaign_id, plan_id, promotions = await _prepare_promoted_assets(client)

    response = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/confirm-execution",
        json={
            "promotion_ids": [item["id"] for item in promotions],
            "confirmation": CONFIRMATION,
            "parallel": False,
            "max_workers": 1,
        },
    )
    assert response.status_code == 202, response.text
    execution_id = response.json()["execution_id"]

    execution = await db_session.get(Execution, execution_id)
    assert execution is not None
    execution.status = ExecutionStatus.PASSED
    execution.passed_cases = execution.total_cases
    execution.failed_cases = 0
    execution.duration_ms = 1200
    await db_session.commit()

    summary = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/execution-summary")

    assert summary.status_code == 200
    body = summary.json()
    assert body["total_executions"] == 1
    assert body["latest_execution_id"] == execution_id
    assert body["latest_status"] == "passed"
    assert body["executions"][0]["execution_id"] == execution_id
    assert body["executions"][0]["pass_rate"] == 1
    assert body["result_breakdown"]["visual_ui"]["total"] >= 1


@pytest.mark.asyncio
async def test_phase4_summary_ignores_other_campaign_executions(client, db_session, monkeypatch) -> None:
    from app.api.v1.endpoints import executions as execution_endpoint

    monkeypatch.setattr(execution_endpoint, "_has_active_celery_workers", lambda: True)
    monkeypatch.setattr(execution_endpoint.execute_test_cases, "apply_async", lambda **kwargs: None)

    campaign_id, plan_id, promotions = await _prepare_promoted_assets(client)

    response = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/confirm-execution",
        json={"promotion_ids": [promotions[0]["id"]], "confirmation": CONFIRMATION},
    )
    assert response.status_code == 202, response.text
    execution_id = response.json()["execution_id"]

    other_execution_id = "EXEC_OTHER_PHASE4"
    db_session.add(
        Execution(
            id=other_execution_id,
            config={"source": "smart_scan_phase3", "campaign_id": "CMP-OTHER", "plan_id": "PLAN-OTHER"},
            status=ExecutionStatus.PASSED,
            total_cases=1,
            passed_cases=1,
        )
    )
    await db_session.commit()

    summary = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/execution-summary")

    assert summary.status_code == 200
    execution_ids = [item["execution_id"] for item in summary.json()["executions"]]
    assert execution_id in execution_ids
    assert other_execution_id not in execution_ids


@pytest.mark.asyncio
async def test_phase4_report_contains_campaign_plan_assets_and_execution(client, monkeypatch) -> None:
    from app.api.v1.endpoints import executions as execution_endpoint

    monkeypatch.setattr(execution_endpoint, "_has_active_celery_workers", lambda: True)
    monkeypatch.setattr(execution_endpoint.execute_test_cases, "apply_async", lambda **kwargs: None)

    campaign_id, plan_id, promotions = await _prepare_promoted_assets(client)
    created = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/confirm-execution",
        json={"promotion_ids": [promotions[0]["id"]], "confirmation": CONFIRMATION},
    )
    assert created.status_code == 202, created.text

    response = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/report")

    assert response.status_code == 200
    body = response.json()
    assert body["campaign"]["id"] == campaign_id
    assert body["plan"]["plan_id"] == plan_id
    assert body["review"]["total"] >= 1
    assert body["assets"]["promotion_count"] >= 1
    assert body["executions"]["total_executions"] == 1
    assert "# Smart Scan Report" in body["markdown"]


@pytest.mark.asyncio
async def test_phase4_report_does_not_require_execution(client) -> None:
    created = await client.post("/api/v1/scan-campaigns", json=_campaign_payload())
    assert created.status_code == 201
    campaign_id = created.json()["id"]
    generated = await client.post(f"/api/v1/scan-campaigns/{campaign_id}/generate-plan", json={})
    assert generated.status_code == 200
    plan_id = generated.json()["plan_id"]

    response = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/report")

    assert response.status_code == 200
    body = response.json()
    assert body["executions"]["total_executions"] == 0
    assert body["campaign"]["id"] == campaign_id
    assert body["plan"]["plan_id"] == plan_id
    assert "尚未创建 Phase 3 执行" in body["markdown"]
