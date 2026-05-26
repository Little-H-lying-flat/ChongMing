from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution, ExecutionStep
from app.models.scan_campaign import ScanCampaignAssetPromotion


CONFIRMATION = "AUTHORIZE_SMART_SCAN_EXECUTION"


def _campaign_payload() -> dict:
    return {
        "name": "JSONPlaceholder Smart Scan Phase 3",
        "target": {
            "base_url": "https://jsonplaceholder.typicode.com/posts",
            "business_module": "Posts Demo",
            "scope_text": "posts read/write demo endpoints",
            "out_of_scope_text": "delete posts, payment, email, sms",
            "notes": "Phase 3 requires explicit authorization",
        },
        "strategy": {
            "scan_mode": "graybox",
            "intensity": "smoke",
            "output_goals": ["formal_assets", "authorized_execution"],
            "generate_asset_drafts": True,
        },
        "boundaries": {
            "allowed_domains": ["jsonplaceholder.typicode.com"],
            "allowed_paths": ["/posts", "/posts/1"],
            "max_pages": 5,
            "max_api_candidates": 10,
            "max_plan_steps": 20,
        },
        "action_policy": {
            "forbidden_actions": ["delete", "payment", "send_sms", "send_email"],
            "confirmation_required_actions": ["POST /posts"],
            "conditional_allowed_actions": ["只允许 public fake REST demo 数据"],
            "form_submit_policy": "confirm_required",
            "write_api_policy": "confirm_required",
        },
        "data_policy": {
            "environment_safety": "sandbox",
            "credential_source": "none",
            "write_policy": "allow_test_data",
            "test_data_markers": ["jsonplaceholder_fake_rest"],
            "cleanup_policy": "not_required_for_fake_rest_demo",
        },
        "special_limits": {},
    }


def _api_asset_payload(method: str, path: str, summary: str) -> dict:
    return {
        "method": method,
        "path": path,
        "summary": summary,
        "tags": ["jsonplaceholder", "posts"],
        "source_name": f"jsonplaceholder-phase3-{method.lower()}",
        "responses": {"200" if method == "GET" else "201": {"description": "OK"}},
    }


async def _counts(db_session: AsyncSession) -> dict[str, int]:
    result = {}
    for name, model in {
        "executions": Execution,
        "execution_steps": ExecutionStep,
    }.items():
        scalar = await db_session.execute(select(func.count()).select_from(model))
        result[name] = scalar.scalar_one()
    return result


async def _prepare_promoted_assets(client, review_choice: str = "approve_for_future_execution") -> tuple[str, str, list[dict]]:
    created = await client.post("/api/v1/scan-campaigns", json=_campaign_payload())
    assert created.status_code == 201
    campaign_id = created.json()["id"]

    read_asset = await client.post(
        "/api/v1/api-assets",
        json=_api_asset_payload("GET", "/posts/1", "Read one public demo post"),
    )
    assert read_asset.status_code == 201
    write_asset = await client.post(
        "/api/v1/api-assets",
        json=_api_asset_payload("POST", "/posts", "Create one fake REST demo post"),
    )
    assert write_asset.status_code == 201

    generated = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/generate-plan",
        json={"notes": "Phase 3 execution contract test"},
    )
    assert generated.status_code == 200
    plan = generated.json()
    plan_id = plan["plan_id"]

    for item in plan["manual_review_items"]:
        response = await client.patch(
            f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/review-items/{item['id']}",
            json={"choice": review_choice, "comment": "Phase 3 review decision"},
        )
        assert response.status_code == 200

    drafts = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/generate-asset-drafts",
        json={"asset_types": ["api_case_ir", "visual_ui_case"], "include_only_approved": True},
    )
    assert drafts.status_code == 200
    draft_items = drafts.json()["asset_drafts"]
    api_draft = next(item for item in draft_items if item["asset_type"] == "api_case_ir_step")
    visual_draft = next(item for item in draft_items if item["asset_type"] == "visual_ui_case")
    selected_draft_ids = [api_draft["id"], visual_draft["id"]]

    promoted = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/promote-asset-drafts",
        json={
            "draft_ids": selected_draft_ids,
            "confirmation": "PROMOTE_SELECTED_DRAFTS",
            "visual_project_id": "phase3-demo",
        },
    )
    assert promoted.status_code == 200
    assert promoted.json()["execution_created"] is False

    promotions = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/asset-drafts/promotions")
    assert promotions.status_code == 200
    promotion_items = promotions.json()["items"]
    assert promotion_items
    return campaign_id, plan_id, promotion_items


@pytest.mark.asyncio
async def test_phase3_requires_explicit_authorization(client, db_session: AsyncSession) -> None:
    campaign_id, plan_id, promotions = await _prepare_promoted_assets(client)
    before = await _counts(db_session)

    response = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/confirm-execution",
        json={"promotion_ids": [promotions[0]["id"]], "confirmation": "WRONG"},
    )

    assert response.status_code == 400
    assert await _counts(db_session) == before


@pytest.mark.asyncio
async def test_phase3_creates_execution_for_api_and_visual_after_authorization(client, db_session: AsyncSession, monkeypatch) -> None:
    from app.api.v1.endpoints import executions as execution_endpoint

    monkeypatch.setattr(execution_endpoint, "_has_active_celery_workers", lambda: True)
    dispatched: dict = {}

    def fake_apply_async(**kwargs):
        dispatched.update(kwargs)

    monkeypatch.setattr(execution_endpoint.execute_test_cases, "apply_async", fake_apply_async)

    campaign_id, plan_id, promotions = await _prepare_promoted_assets(client)
    before = await _counts(db_session)

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
    body = response.json()
    assert body["execution_created"] is True
    assert body["execution_id"].startswith("EXEC_")
    assert body["total_cases"] == len(body["tc_ids"])
    assert body["dynamic_payload_count"] >= 1

    after = await _counts(db_session)
    assert after["executions"] == before["executions"] + 1
    assert after["execution_steps"] == before["execution_steps"]
    assert dispatched["kwargs"]["execution_id"] == body["execution_id"]
    assert dispatched["kwargs"]["dynamic_payload"]

    execution = await db_session.get(Execution, body["execution_id"])
    assert execution is not None
    assert execution.config["source"] == "smart_scan_phase3"
    assert execution.config["campaign_id"] == campaign_id
    assert execution.config["plan_id"] == plan_id
    assert execution.config["authorization"]["confirmation"] == CONFIRMATION
    assert execution.config["dynamic_payload_count"] >= 1


@pytest.mark.asyncio
async def test_phase3_blocks_generate_asset_only_for_risky_write_item(client, db_session: AsyncSession) -> None:
    campaign_id, plan_id, promotions = await _prepare_promoted_assets(client, review_choice="generate_asset_only")
    before = await _counts(db_session)
    risky_promotions = [item for item in promotions if item["promotion_metadata"].get("policy") in {"confirmation_required", "conditional_allowed"}]
    assert risky_promotions

    response = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/confirm-execution",
        json={"promotion_ids": [risky_promotions[0]["id"]], "confirmation": CONFIRMATION},
    )

    assert response.status_code == 400
    assert await _counts(db_session) == before


@pytest.mark.asyncio
async def test_phase3_blocks_unknown_promotion_without_execution(client, db_session: AsyncSession) -> None:
    campaign_id, plan_id, _ = await _prepare_promoted_assets(client)
    before = await _counts(db_session)

    response = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/confirm-execution",
        json={"promotion_ids": ["PROMO-NOPE"], "confirmation": CONFIRMATION},
    )

    assert response.status_code == 400
    assert await _counts(db_session) == before
