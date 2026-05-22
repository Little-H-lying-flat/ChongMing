from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution, ExecutionStep
from app.models.scan_campaign import ScanCampaignAssetDraft, ScanCampaignPlan, ScanCampaignReviewItem
from app.models.test_case import TestCase as CaseModel
from app.models.visual_ui import VisualStep, VisualUseCase


def _campaign_payload(name: str = "用户管理 Smoke 灰盒扫描") -> dict:
    return {
        "name": name,
        "target": {
            "base_url": "https://staging.example.com",
            "business_module": "用户管理",
            "scope_text": "登录、用户列表、新建用户",
            "out_of_scope_text": "删除用户、重置密码、发送邀请短信",
            "notes": "Phase 1 只生成计划，不执行",
        },
        "strategy": {
            "scan_mode": "graybox",
            "intensity": "smoke",
            "output_goals": ["test_plan", "pre_execution_checklist"],
            "generate_asset_drafts": False,
        },
        "boundaries": {
            "allowed_domains": ["staging.example.com"],
            "allowed_paths": ["/login", "/users", "/api/users"],
            "max_pages": 10,
            "max_api_candidates": 20,
            "max_plan_steps": 30,
        },
        "action_policy": {
            "forbidden_actions": ["delete", "payment", "send_sms", "send_email"],
            "confirmation_required_actions": ["POST /api/users"],
            "conditional_allowed_actions": ["仅允许写入 test_user_* 测试数据"],
            "form_submit_policy": "confirm_required",
            "write_api_policy": "confirm_required",
        },
        "data_policy": {
            "environment_safety": "staging",
            "credential_source": "environment",
            "write_policy": "allow_test_data",
            "test_data_markers": ["test_user_*"],
            "cleanup_policy": "manual_cleanup",
        },
        "special_limits": {
            "upload": {"allowed_types": ["png", "jpg"], "max_size_mb": 2},
            "export": {"max_rows": 100, "field_allowlist": ["id"]},
            "payment": {"provider_policy": "mock_or_sandbox_only"},
        },
    }


def _api_asset_payload(method: str, path: str, summary: str) -> dict:
    return {
        "method": method,
        "path": path,
        "summary": summary,
        "tags": ["users"],
        "source_name": "user-service",
        "responses": {"200" if method == "GET" else "201": {"description": "OK"}},
    }


async def _table_counts(db_session: AsyncSession) -> dict[str, int]:
    result: dict[str, int] = {}
    for name, model in {
        "executions": Execution,
        "execution_steps": ExecutionStep,
        "test_cases": CaseModel,
        "visual_use_cases": VisualUseCase,
        "visual_steps": VisualStep,
    }.items():
        scalar = await db_session.execute(select(func.count()).select_from(model))
        result[name] = scalar.scalar_one()
    return result


@pytest.mark.asyncio
async def test_scan_campaign_plan_review_and_asset_draft_flow(client, db_session: AsyncSession) -> None:
    created = await client.post("/api/v1/scan-campaigns", json=_campaign_payload())
    assert created.status_code == 201
    campaign = created.json()
    assert campaign["status"] == "draft"
    campaign_id = campaign["id"]

    listed = await client.get("/api/v1/scan-campaigns?page=1&page_size=20&scan_mode=graybox")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = await client.put(
        f"/api/v1/scan-campaigns/{campaign_id}",
        json={"name": "用户管理 Smoke 灰盒扫描 v2"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"].endswith("v2")

    get_asset = await client.post(
        "/api/v1/api-assets",
        json=_api_asset_payload("GET", "/api/users", "List users"),
    )
    assert get_asset.status_code == 201
    post_asset = await client.post(
        "/api/v1/api-assets",
        json=_api_asset_payload("POST", "/api/users", "Create user"),
    )
    assert post_asset.status_code == 201
    delete_asset = await client.post(
        "/api/v1/api-assets",
        json=_api_asset_payload("DELETE", "/api/users/{id}", "Delete user"),
    )
    assert delete_asset.status_code == 201

    before_plan_counts = await _table_counts(db_session)
    generated = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/generate-plan",
        json={"notes": "优先复用 API Asset"},
    )
    assert generated.status_code == 200
    after_plan_counts = await _table_counts(db_session)
    assert after_plan_counts == before_plan_counts

    plan = generated.json()
    assert plan["campaign_draft_id"] == campaign_id
    assert plan["version"] == 1
    assert plan["summary"]["execution_state"] == "not_executed"
    assert plan["api_candidates"]
    assert plan["ui_flows"]
    assert plan["risk_items"]
    assert plan["coverage_summary"]["api_candidate_count"] >= 2
    assert any(candidate["policy"] == "allowed" for candidate in plan["api_candidates"])
    assert any(candidate["policy"] == "confirmation_required" for candidate in plan["api_candidates"])
    assert any(item["policy"] == "forbidden" for item in plan["risk_items"])

    plan_id = plan["plan_id"]
    blocked_update = await client.put(
        f"/api/v1/scan-campaigns/{campaign_id}",
        json={"name": "should not update"},
    )
    assert blocked_update.status_code == 409

    duplicate_plan = await client.post(f"/api/v1/scan-campaigns/{campaign_id}/generate-plan", json={})
    assert duplicate_plan.status_code == 409

    review_items = plan["manual_review_items"]
    assert review_items
    review_id = review_items[0]["id"]
    before_review_counts = await _table_counts(db_session)
    review = await client.patch(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/review-items/{review_id}",
        json={"choice": "generate_asset_only", "comment": "只生成草稿"},
    )
    assert review.status_code == 200
    after_review_counts = await _table_counts(db_session)
    assert after_review_counts == before_review_counts
    assert review.json()["item"]["choice"] == "generate_asset_only"

    before_draft_counts = await _table_counts(db_session)
    drafts = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/plans/{plan_id}/generate-asset-drafts",
        json={"asset_types": ["api_case_ir", "visual_ui_case"], "include_only_approved": True},
    )
    assert drafts.status_code == 200
    after_draft_counts = await _table_counts(db_session)
    assert after_draft_counts == before_draft_counts

    draft_body = drafts.json()
    assert draft_body["api_case_ir_steps"]
    api_step = draft_body["api_case_ir_steps"][0]
    assert api_step["protocol"] == "API-IR"
    assert api_step["version"] == "2.0"
    assert api_step["step_type"] == "API"
    assert api_step["metadata"]["source_type"] == "scan_campaign"
    assert api_step["metadata"]["campaign_id"] == campaign_id
    assert api_step["metadata"]["plan_id"] == plan_id
    assert api_step["metadata"]["execution_allowed_in_phase"] is False
    assert draft_body["visual_ui_cases"]
    assert draft_body["visual_ui_cases"][0]["metadata"]["execution_allowed_in_phase"] is False
    assert draft_body["skipped_items"]

    draft_count = await db_session.execute(select(func.count()).select_from(ScanCampaignAssetDraft))
    assert draft_count.scalar_one() >= 2

    latest = await client.get(f"/api/v1/scan-campaigns/{campaign_id}/plan")
    assert latest.status_code == 200
    assert latest.json()["status"] == "asset_drafts_generated"

    regenerated = await client.post(
        f"/api/v1/scan-campaigns/{campaign_id}/generate-plan",
        json={"regenerate": True},
    )
    assert regenerated.status_code == 200
    assert regenerated.json()["version"] == 2

    old_plan = await db_session.execute(select(ScanCampaignPlan).where(ScanCampaignPlan.id == plan_id))
    assert old_plan.scalar_one().status.value == "superseded"

    for forbidden_path in ("execute", "run", "schedule", "crawl-all", "attack-scan"):
        response = await client.post(f"/api/v1/scan-campaigns/{campaign_id}/{forbidden_path}")
        assert response.status_code in {404, 405}

    deleted = await client.delete(f"/api/v1/scan-campaigns/{campaign_id}")
    assert deleted.status_code == 204
    remaining_plans = await db_session.execute(select(func.count()).select_from(ScanCampaignPlan))
    remaining_reviews = await db_session.execute(select(func.count()).select_from(ScanCampaignReviewItem))
    remaining_drafts = await db_session.execute(select(func.count()).select_from(ScanCampaignAssetDraft))
    assert remaining_plans.scalar_one() == 0
    assert remaining_reviews.scalar_one() == 0
    assert remaining_drafts.scalar_one() == 0


@pytest.mark.asyncio
async def test_scan_campaign_boundary_validation(client) -> None:
    missing_domains = _campaign_payload()
    missing_domains["boundaries"]["allowed_domains"] = []
    response = await client.post("/api/v1/scan-campaigns", json=missing_domains)
    assert response.status_code == 400

    wildcard_domains = _campaign_payload()
    wildcard_domains["boundaries"]["allowed_domains"] = ["*"]
    response = await client.post("/api/v1/scan-campaigns", json=wildcard_domains)
    assert response.status_code == 400

    wrong_domain = _campaign_payload()
    wrong_domain["target"]["base_url"] = "https://prod.example.org"
    response = await client.post("/api/v1/scan-campaigns", json=wrong_domain)
    assert response.status_code == 400

    empty_paths = _campaign_payload()
    empty_paths["boundaries"]["allowed_paths"] = []
    response = await client.post("/api/v1/scan-campaigns", json=empty_paths)
    assert response.status_code == 400
