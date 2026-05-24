from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution, ExecutionStep
from app.models.scan_campaign import ScanCampaignAssetPromotion
from app.models.test_case import TestCase as CaseModel
from app.models.visual_ui import VisualStep, VisualUseCase


def _campaign_payload() -> dict:
    return {
        "name": "JSONPlaceholder Smart Scan Phase 2",
        "target": {
            "base_url": "https://jsonplaceholder.typicode.com",
            "business_module": "Posts Demo",
            "scope_text": "posts read/write demo endpoints",
            "out_of_scope_text": "delete posts, payment, email, sms",
            "notes": "Phase 2 只保存正式资产，不执行",
        },
        "strategy": {
            "scan_mode": "graybox",
            "intensity": "smoke",
            "output_goals": ["formal_assets"],
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
        "source_name": "jsonplaceholder-demo",
        "responses": {"200" if method == "GET" else "201": {"description": "OK"}},
    }


async def _counts(db_session: AsyncSession) -> dict[str, int]:
    result = {}
    for name, model in {
        "executions": Execution,
        "execution_steps": ExecutionStep,
        "test_cases": CaseModel,
        "visual_use_cases": VisualUseCase,
        "visual_steps": VisualStep,
        "promotions": ScanCampaignAssetPromotion,
    }.items():
        scalar = await db_session.execute(select(func.count()).select_from(model))
        result[name] = scalar.scalar_one()
    return result


@pytest.mark.asyncio
async def test_promote_asset_drafts_creates_formal_assets_without_execution(client, db_session: AsyncSession) -> None:
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
        json={"notes": "Phase 2 promote contract test"},
    )
    assert generated.status_code == 200
    plan = generated.json()
    plan_id = plan["plan_id"]

    for item in plan["manual_review_items"]:
        response = await client.patch(
            f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/review-items/{item['id']}",
            json={"choice": "generate_asset_only", "comment": "保存正式资产，不执行"},
        )
        assert response.status_code == 200

    drafts = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/generate-asset-drafts",
        json={"asset_types": ["api_case_ir", "visual_ui_case"], "include_only_approved": True},
    )
    assert drafts.status_code == 200

    listed = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/asset-drafts")
    assert listed.status_code == 200
    draft_items = listed.json()["items"]
    api_draft = next(item for item in draft_items if item["asset_type"] == "api_case_ir_step")
    visual_draft = next(item for item in draft_items if item["asset_type"] == "visual_ui_case")

    before = await _counts(db_session)
    promoted = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/promote-asset-drafts",
        json={
            "draft_ids": [api_draft["id"], visual_draft["id"]],
            "confirmation": "PROMOTE_SELECTED_DRAFTS",
            "visual_project_id": "phase2-demo",
        },
    )
    assert promoted.status_code == 200
    body = promoted.json()
    assert body["execution_created"] is False
    assert len(body["promoted"]) == 2
    assert body["duplicates"] == []
    assert body["failed"] == []

    after = await _counts(db_session)
    assert after["executions"] == before["executions"]
    assert after["execution_steps"] == before["execution_steps"]
    assert after["test_cases"] == before["test_cases"] + 1
    assert after["visual_use_cases"] == before["visual_use_cases"] + 1
    assert after["visual_steps"] > before["visual_steps"]
    assert after["promotions"] == before["promotions"] + 2

    case_result = await db_session.execute(select(CaseModel).where(CaseModel.source_id == api_draft["id"]))
    case = case_result.scalar_one()
    assert case.source_type == "scan_campaign_asset_draft"
    assert case.steps[0]["protocol"] == "API-IR"
    assert case.steps[0]["version"] == "2.0"
    assert case.steps[0]["metadata"]["campaign_id"] == campaign_id
    assert case.steps[0]["metadata"]["plan_id"] == plan_id
    assert case.steps[0]["metadata"]["asset_draft_id"] == api_draft["id"]
    assert case.steps[0]["metadata"]["execution_allowed_in_phase"] is False

    promotions = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/asset-drafts/promotions")
    assert promotions.status_code == 200
    assert len(promotions.json()["items"]) == 2

    duplicate = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/promote-asset-drafts",
        json={"draft_ids": [api_draft["id"]], "confirmation": "PROMOTE_SELECTED_DRAFTS"},
    )
    assert duplicate.status_code == 200
    duplicate_body = duplicate.json()
    assert len(duplicate_body["duplicates"]) == 1
    assert duplicate_body["duplicates"][0]["reason"] == "already_promoted"
    duplicate_counts = await _counts(db_session)
    assert duplicate_counts == after


@pytest.mark.asyncio
async def test_promote_asset_drafts_requires_explicit_confirmation(client) -> None:
    created = await client.post("/api/v1/scan-campaigns", json=_campaign_payload())
    assert created.status_code == 201
    campaign_id = created.json()["id"]
    generated = await client.post(f"/api/v1/scan-campaigns/{campaign_id}/generate-plan", json={})
    assert generated.status_code == 200
    plan_id = generated.json()["plan_id"]

    response = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/promote-asset-drafts",
        json={"draft_ids": ["DRAFT-NOPE"], "confirmation": "WRONG"},
    )
    assert response.status_code == 400
