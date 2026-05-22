"""Service layer for Scan Campaign Phase 1 APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_asset import ApiAsset
from app.models.scan_campaign import (
    ScanCampaign,
    ScanCampaignAssetDraft,
    ScanCampaignPlan,
    ScanCampaignPlanStatus,
    ScanCampaignReviewChoice,
    ScanCampaignReviewItem,
    ScanCampaignStatus,
)
from app.services.api_case_ir_converter import normalize_api_step_v2


class ScanCampaignConflictError(ValueError):
    pass


class ScanCampaignNotFoundError(ValueError):
    pass


class ScanCampaignValidationError(ValueError):
    pass


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}
FORBIDDEN_KEYWORDS = (
    "delete",
    "payment",
    "pay",
    "charge",
    "refund",
    "sms",
    "email",
    "invite",
    "permission",
    "role",
    "admin",
    "reset-password",
)


class ScanCampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any]) -> ScanCampaign:
        payload = self._prepare_campaign_payload(data)
        payload["id"] = payload.get("id") or self._new_id("CMP")
        payload["status"] = ScanCampaignStatus.DRAFT
        db_obj = ScanCampaign(**payload)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def get(self, campaign_id: str) -> Optional[ScanCampaign]:
        result = await self.db.execute(select(ScanCampaign).where(ScanCampaign.id == campaign_id))
        return result.scalars().first()

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        scan_mode: Optional[str] = None,
    ) -> List[ScanCampaign]:
        query = self._apply_campaign_filters(
            select(ScanCampaign), status=status, keyword=keyword, scan_mode=scan_mode
        )
        query = query.order_by(ScanCampaign.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(
        self,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        scan_mode: Optional[str] = None,
    ) -> int:
        query = self._apply_campaign_filters(
            select(func.count(ScanCampaign.id)), status=status, keyword=keyword, scan_mode=scan_mode
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    async def update(self, campaign_id: str, data: Dict[str, Any]) -> Optional[ScanCampaign]:
        existing = await self.get(campaign_id)
        if existing is None:
            return None
        if existing.status not in {ScanCampaignStatus.DRAFT, ScanCampaignStatus.NEEDS_REVISION}:
            raise ScanCampaignConflictError("只有 draft 或 needs_revision 状态允许修改 Campaign")

        merged = self._campaign_to_payload(existing)
        merged.update({key: value for key, value in data.items() if value is not None})
        payload = self._prepare_campaign_payload(merged)
        for key, value in payload.items():
            if key not in {"id", "status", "ai_plan_id", "created_at"}:
                setattr(existing, key, value)
        existing.updated_at = self._utcnow()
        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def delete(self, campaign_id: str) -> bool:
        existing = await self.get(campaign_id)
        if existing is None:
            return False
        await self.db.delete(existing)
        await self.db.commit()
        return True

    async def generate_plan(
        self,
        campaign_id: str,
        regenerate: bool = False,
        notes: Optional[str] = None,
    ) -> ScanCampaignPlan:
        campaign = await self.get(campaign_id)
        if campaign is None:
            raise ScanCampaignNotFoundError(f"Campaign {campaign_id} not found")

        latest = await self.get_latest_plan(campaign_id)
        if latest and not regenerate:
            raise ScanCampaignConflictError("Campaign 已存在最新 plan，请使用 regenerate=true 重新生成")
        if latest and regenerate:
            latest.status = ScanCampaignPlanStatus.SUPERSEDED

        version = await self._next_plan_version(campaign_id)
        api_candidates = await self._build_api_candidates(campaign)
        ui_flows = self._build_ui_flows(campaign)
        risk_items = self._build_scope_risk_items(campaign)
        manual_review_payloads: list[dict[str, Any]] = []

        for candidate in api_candidates:
            policy = candidate.get("policy")
            if policy in {"forbidden", "out_of_scope"}:
                risk_items.append(self._risk_item_from_candidate(candidate))
            elif policy in {"confirmation_required", "conditional_allowed"}:
                manual_review_payloads.append(self._review_item_from_candidate(candidate))

        for flow in ui_flows:
            for step in flow.get("steps", []):
                if step.get("requires_confirmation"):
                    manual_review_payloads.append(self._review_item_from_ui_step(flow, step))

        plan = ScanCampaignPlan(
            id=self._new_id("PLAN"),
            campaign_id=campaign.id,
            version=version,
            status=ScanCampaignPlanStatus.GENERATED,
            summary=self._build_summary(campaign, api_candidates, risk_items),
            scope_review=self._build_scope_review(campaign, risk_items),
            ui_flows=ui_flows,
            api_candidates=api_candidates,
            risk_items=risk_items,
            coverage_summary=self._build_coverage_summary(ui_flows, api_candidates, risk_items),
            generation_metadata={
                "generator": "deterministic_phase1",
                "notes": notes,
                "campaign_snapshot": self._campaign_snapshot(campaign),
                "source_counts": {"api_asset": len(api_candidates), "ai_generated_ui_flow": len(ui_flows)},
            },
        )
        self.db.add(plan)
        await self.db.flush()

        for payload in manual_review_payloads:
            self.db.add(
                ScanCampaignReviewItem(
                    id=self._new_id("REVIEW"),
                    campaign_id=campaign.id,
                    plan_id=plan.id,
                    **payload,
                )
            )

        campaign.status = ScanCampaignStatus.PLAN_GENERATED
        campaign.ai_plan_id = plan.id
        campaign.updated_at = self._utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def get_latest_plan(self, campaign_id: str) -> Optional[ScanCampaignPlan]:
        result = await self.db.execute(
            select(ScanCampaignPlan)
            .where(
                ScanCampaignPlan.campaign_id == campaign_id,
                ScanCampaignPlan.status != ScanCampaignPlanStatus.SUPERSEDED,
            )
            .order_by(ScanCampaignPlan.version.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_plan(self, campaign_id: str, plan_id: str) -> Optional[ScanCampaignPlan]:
        result = await self.db.execute(
            select(ScanCampaignPlan).where(
                ScanCampaignPlan.campaign_id == campaign_id,
                ScanCampaignPlan.id == plan_id,
            )
        )
        return result.scalars().first()

    async def list_review_items(self, plan_id: str) -> List[ScanCampaignReviewItem]:
        result = await self.db.execute(
            select(ScanCampaignReviewItem)
            .where(ScanCampaignReviewItem.plan_id == plan_id)
            .order_by(ScanCampaignReviewItem.created_at.asc())
        )
        return result.scalars().all()

    async def list_asset_drafts(self, plan_id: str) -> List[ScanCampaignAssetDraft]:
        result = await self.db.execute(
            select(ScanCampaignAssetDraft)
            .where(ScanCampaignAssetDraft.plan_id == plan_id)
            .order_by(ScanCampaignAssetDraft.created_at.asc())
        )
        return result.scalars().all()

    async def update_review_item(
        self,
        campaign_id: str,
        plan_id: str,
        review_item_id: str,
        choice: str,
        comment: Optional[str] = None,
    ) -> tuple[ScanCampaignReviewItem, str]:
        plan = await self.get_plan(campaign_id, plan_id)
        if plan is None:
            raise ScanCampaignNotFoundError(f"Plan {plan_id} not found")

        result = await self.db.execute(
            select(ScanCampaignReviewItem).where(
                ScanCampaignReviewItem.campaign_id == campaign_id,
                ScanCampaignReviewItem.plan_id == plan_id,
                ScanCampaignReviewItem.id == review_item_id,
            )
        )
        item = result.scalars().first()
        if item is None:
            raise ScanCampaignNotFoundError(f"Review item {review_item_id} not found")
        if choice not in (item.available_choices or []):
            raise ScanCampaignValidationError("choice 不在 available_choices 中")

        item.choice = ScanCampaignReviewChoice(choice)
        item.comment = comment
        item.choice_updated_at = self._utcnow()
        item.updated_at = self._utcnow()
        await self.db.flush()

        items = await self.list_review_items(plan_id)
        if all(self._enum_value(review.choice) != ScanCampaignReviewChoice.PENDING.value for review in items):
            plan.status = ScanCampaignPlanStatus.REVIEW_SAVED
            plan.updated_at = self._utcnow()
        await self.db.commit()
        await self.db.refresh(item)
        await self.db.refresh(plan)
        return item, self._enum_value(plan.status)

    async def generate_asset_drafts(
        self,
        campaign_id: str,
        plan_id: str,
        asset_types: List[str],
        include_only_approved: bool = True,
    ) -> Dict[str, Any]:
        campaign = await self.get(campaign_id)
        plan = await self.get_plan(campaign_id, plan_id)
        if campaign is None:
            raise ScanCampaignNotFoundError(f"Campaign {campaign_id} not found")
        if plan is None:
            raise ScanCampaignNotFoundError(f"Plan {plan_id} not found")

        await self.db.execute(delete(ScanCampaignAssetDraft).where(ScanCampaignAssetDraft.plan_id == plan_id))
        review_items = await self.list_review_items(plan_id)
        review_by_target = {item.target_id: item for item in review_items}
        requested = set(asset_types or [])
        api_steps: list[dict[str, Any]] = []
        visual_cases: list[dict[str, Any]] = []
        skipped_items: list[dict[str, Any]] = []
        db_drafts: list[ScanCampaignAssetDraft] = []

        if "api_case_ir" in requested:
            for candidate in plan.api_candidates or []:
                if not self._can_generate_candidate(candidate, review_by_target, include_only_approved):
                    skipped_items.append(self._skipped_item(candidate, "policy_or_review_not_approved"))
                    continue
                step = self._build_api_ir_step(candidate, campaign, plan, review_by_target.get(candidate.get("id")))
                api_steps.append(step)
                db_drafts.append(
                    self._asset_draft_model(
                        campaign_id=campaign_id,
                        plan_id=plan_id,
                        asset_type="api_case_ir_step",
                        source_type=str(candidate.get("source") or "api_asset"),
                        source_item_id=str(candidate.get("id")),
                        policy=str(candidate.get("policy")),
                        risk_level=candidate.get("risk_level"),
                        draft_payload=step,
                        draft_metadata=step.get("metadata") or {},
                    )
                )

        if "visual_ui_case" in requested:
            for flow in plan.ui_flows or []:
                if not self._can_generate_flow(flow, review_by_target, include_only_approved):
                    skipped_items.append({"target": flow.get("id"), "reason": "ui_flow_review_not_approved"})
                    continue
                ui_case = self._build_visual_ui_case(flow, campaign, plan)
                visual_cases.append(ui_case)
                db_drafts.append(
                    self._asset_draft_model(
                        campaign_id=campaign_id,
                        plan_id=plan_id,
                        asset_type="visual_ui_case",
                        source_type=str(flow.get("source") or "ai_generated"),
                        source_item_id=str(flow.get("id")),
                        policy=str(flow.get("policy") or "allowed"),
                        risk_level=flow.get("risk_level"),
                        draft_payload=ui_case,
                        draft_metadata=ui_case.get("metadata") or {},
                    )
                )

        for risk in plan.risk_items or []:
            if risk.get("policy") in {"forbidden", "out_of_scope"}:
                skipped_items.append({"target": risk.get("target"), "policy": risk.get("policy"), "reason": risk.get("reason")})

        for draft in db_drafts:
            self.db.add(draft)
        plan.status = ScanCampaignPlanStatus.ASSET_DRAFTS_GENERATED
        plan.updated_at = self._utcnow()
        await self.db.commit()
        for draft in db_drafts:
            await self.db.refresh(draft)
        return {
            "api_case_ir_steps": api_steps,
            "visual_ui_cases": visual_cases,
            "skipped_items": skipped_items,
            "asset_drafts": db_drafts,
        }

    def build_plan_response(
        self,
        plan: ScanCampaignPlan,
        review_items: List[ScanCampaignReviewItem],
        asset_drafts: Optional[List[ScanCampaignAssetDraft]] = None,
    ) -> Dict[str, Any]:
        return {
            "plan_id": plan.id,
            "campaign_draft_id": plan.campaign_id,
            "version": plan.version,
            "status": self._enum_value(plan.status),
            "summary": plan.summary or {},
            "scope_review": plan.scope_review or {},
            "ui_flows": plan.ui_flows or [],
            "api_candidates": plan.api_candidates or [],
            "risk_items": plan.risk_items or [],
            "manual_review_items": [self.review_item_to_response(item) for item in review_items],
            "asset_drafts": self._asset_draft_summary(asset_drafts or []),
            "coverage_summary": plan.coverage_summary or {},
            "generation_metadata": plan.generation_metadata or {},
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

    def campaign_to_response(self, campaign: ScanCampaign) -> Dict[str, Any]:
        return {
            "id": campaign.id,
            "name": campaign.name,
            "status": self._enum_value(campaign.status),
            "target": campaign.target or {},
            "strategy": campaign.strategy or {},
            "boundaries": campaign.boundaries or {},
            "action_policy": campaign.action_policy or {},
            "data_policy": campaign.data_policy or {},
            "special_limits": campaign.special_limits or {},
            "ai_plan_id": campaign.ai_plan_id,
            "created_at": campaign.created_at,
            "updated_at": campaign.updated_at,
        }

    def review_item_to_response(self, item: ScanCampaignReviewItem) -> Dict[str, Any]:
        return {
            "id": item.id,
            "campaign_id": item.campaign_id,
            "plan_id": item.plan_id,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "policy": item.policy,
            "title": item.title,
            "reason": item.reason,
            "if_approved": item.if_approved,
            "if_rejected": item.if_rejected,
            "available_choices": item.available_choices or [],
            "choice": self._enum_value(item.choice),
            "comment": item.comment,
            "choice_updated_at": item.choice_updated_at,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def asset_draft_to_response(self, draft: ScanCampaignAssetDraft) -> Dict[str, Any]:
        return {
            "id": draft.id,
            "campaign_id": draft.campaign_id,
            "plan_id": draft.plan_id,
            "asset_type": draft.asset_type,
            "source_type": draft.source_type,
            "source_item_id": draft.source_item_id,
            "policy": draft.policy,
            "risk_level": draft.risk_level,
            "draft_payload": draft.draft_payload or {},
            "metadata": draft.draft_metadata or {},
            "skipped_reason": draft.skipped_reason,
            "created_at": draft.created_at,
        }

    def _prepare_campaign_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(data)
        payload["target"] = payload.get("target") or {}
        payload["strategy"] = payload.get("strategy") or {}
        payload["boundaries"] = payload.get("boundaries") or {}
        payload["action_policy"] = payload.get("action_policy") or {}
        payload["data_policy"] = payload.get("data_policy") or {}
        payload["special_limits"] = payload.get("special_limits") or {}
        self._validate_campaign_payload(payload)
        payload["search_text"] = self._build_search_text(payload)
        return payload

    def _validate_campaign_payload(self, payload: Dict[str, Any]) -> None:
        if not str(payload.get("name") or "").strip():
            raise ScanCampaignValidationError("Campaign name is required")
        target = payload.get("target") or {}
        boundaries = payload.get("boundaries") or {}
        base_url = str(target.get("base_url") or "").strip()
        if not base_url:
            raise ScanCampaignValidationError("target.base_url is required")
        allowed_domains = self._string_list(boundaries.get("allowed_domains"))
        if not allowed_domains or any(domain in {"*", ""} for domain in allowed_domains):
            raise ScanCampaignValidationError("boundaries.allowed_domains 至少包含一个明确域名")
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        if not host or not any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains):
            raise ScanCampaignValidationError("target.base_url 必须命中 allowed_domains")
        allowed_paths = self._string_list(boundaries.get("allowed_paths"))
        if not allowed_paths:
            raise ScanCampaignValidationError("boundaries.allowed_paths 至少包含一个路径")
        for field, limit in (("max_pages", 100), ("max_api_candidates", 200), ("max_plan_steps", 300)):
            value = int(boundaries.get(field) or 0)
            if value <= 0 or value > limit:
                raise ScanCampaignValidationError(f"boundaries.{field} 必须在 1 到 {limit} 之间")

    def _apply_campaign_filters(self, query, **filters):
        status = filters.get("status")
        keyword = filters.get("keyword")
        scan_mode = filters.get("scan_mode")
        if status:
            query = query.where(ScanCampaign.status == ScanCampaignStatus(status))
        if keyword:
            query = query.where(ScanCampaign.search_text.like(f"%{keyword.strip().lower()}%"))
        if scan_mode:
            query = query.where(ScanCampaign.search_text.like(f"%scan_mode:{scan_mode.strip().lower()}%"))
        return query

    async def _build_api_candidates(self, campaign: ScanCampaign) -> List[Dict[str, Any]]:
        allowed_paths = self._string_list((campaign.boundaries or {}).get("allowed_paths"))
        max_candidates = int((campaign.boundaries or {}).get("max_api_candidates") or 20)
        query = select(ApiAsset).where(ApiAsset.deprecated == False).order_by(ApiAsset.updated_at.desc())
        result = await self.db.execute(query)
        candidates: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for asset in result.scalars().all():
            base = self._candidate_from_asset(asset)
            policy_result = self.evaluate_api_candidate_policy(base, campaign)
            base.update(policy_result)
            if base["policy"] == "out_of_scope":
                blocked.append(base)
                continue
            candidates.append(base)
            if len(candidates) >= max_candidates:
                break
        return candidates + blocked[: max(0, max_candidates - len(candidates))]

    def evaluate_api_candidate_policy(self, candidate: Dict[str, Any], campaign: ScanCampaign) -> Dict[str, Any]:
        method = str(candidate.get("method") or "GET").upper()
        path = str(candidate.get("path") or "/")
        target_text = f"{method} {path} {candidate.get('operation_id') or ''} {candidate.get('summary') or ''}".lower()
        environment = str((campaign.data_policy or {}).get("environment_safety") or "").lower()
        conditions = self._conditions_for_candidate(candidate, campaign)

        if not self._is_path_allowed(path, self._string_list((campaign.boundaries or {}).get("allowed_paths"))):
            return {
                "policy": "out_of_scope",
                "risk_level": "medium",
                "risk_reason": "接口路径超出 allowed_paths",
                "conditions": conditions,
                "can_generate_api_case_ir": False,
            }
        if method == "DELETE" or any(keyword in target_text for keyword in FORBIDDEN_KEYWORDS):
            return {
                "policy": "forbidden",
                "risk_level": "high",
                "risk_reason": "命中默认禁止动作或高风险业务动作",
                "conditions": conditions,
                "can_generate_api_case_ir": False,
            }
        if method in WRITE_METHODS:
            if environment == "production-readonly":
                return {
                    "policy": "forbidden",
                    "risk_level": "high",
                    "risk_reason": "production-readonly 环境禁止写操作",
                    "conditions": conditions,
                    "can_generate_api_case_ir": False,
                }
            return {
                "policy": "confirmation_required",
                "risk_level": "medium",
                "risk_reason": "写操作会修改测试数据，必须人工确认",
                "conditions": conditions,
                "can_generate_api_case_ir": True,
            }
        return {
            "policy": "allowed",
            "risk_level": "low",
            "risk_reason": "只读接口且命中 Campaign 范围",
            "conditions": conditions,
            "can_generate_api_case_ir": True,
        }

    def _candidate_from_asset(self, asset: ApiAsset) -> Dict[str, Any]:
        return {
            "id": f"API_CANDIDATE_{asset.id}",
            "natural_language_step": asset.summary or asset.name or f"{asset.method} {asset.path}",
            "method": asset.method,
            "path": asset.path,
            "source": "api_asset",
            "source_ref": {
                "asset_id": asset.id,
                "asset_key": asset.asset_key,
                "source_name": asset.source_name,
                "operation_id": asset.operation_id,
            },
            "operation_id": asset.operation_id,
            "summary": asset.summary,
            "match_score": 0.9,
            "match_reasons": [
                f"path 命中 {asset.path}",
                "source=api_asset 可信度高",
                f"method={asset.method} 来自接口资产库",
            ],
            "recommended_assertions": [
                {"type": "status_code", "expected": self._default_status_code(asset.responses)},
            ],
            "recommended_extractions": {},
        }

    def _build_ui_flows(self, campaign: ScanCampaign) -> List[Dict[str, Any]]:
        target = campaign.target or {}
        allowed_paths = self._string_list((campaign.boundaries or {}).get("allowed_paths"))
        first_path = allowed_paths[0] if allowed_paths else "/"
        return [
            {
                "id": "UI_FLOW_001",
                "name": f"{target.get('business_module') or campaign.name} 范围冒烟流程",
                "source": "ai_generated",
                "policy": "allowed",
                "risk_level": "low",
                "steps": [
                    {
                        "id": "UI_STEP_001",
                        "action": "GOTO",
                        "target": first_path,
                        "description": "打开 Campaign 范围内的入口页面",
                        "policy": "allowed",
                        "risk_level": "low",
                        "requires_confirmation": False,
                    },
                    {
                        "id": "UI_STEP_002",
                        "action": "ASSERT",
                        "target": target.get("business_module") or campaign.name,
                        "description": "确认目标模块页面可见",
                        "policy": "allowed",
                        "risk_level": "low",
                        "requires_confirmation": False,
                    },
                ],
                "assertions": ["页面能正常打开", "目标模块内容可见"],
                "can_generate_visual_case": True,
            }
        ]

    def _build_scope_risk_items(self, campaign: ScanCampaign) -> List[Dict[str, Any]]:
        excluded = str((campaign.target or {}).get("out_of_scope_text") or "").strip()
        if not excluded:
            return []
        return [
            {
                "id": "RISK_SCOPE_001",
                "target": excluded,
                "category": "user_excluded_scope",
                "policy": "forbidden",
                "severity": "medium",
                "reason": "用户明确列为不测试范围",
                "user_visible_message": "该范围只展示为不执行项，不会生成可执行 step。",
                "resolution": "如需覆盖，请修改 Campaign 范围后重新生成计划。",
            }
        ]

    def _risk_item_from_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": f"RISK_{candidate.get('id')}",
            "target": f"{candidate.get('method')} {candidate.get('path')}",
            "category": "api_candidate_policy",
            "policy": candidate.get("policy"),
            "severity": "high" if candidate.get("policy") == "forbidden" else "medium",
            "reason": candidate.get("risk_reason") or "候选接口被后端策略拦截",
            "user_visible_message": "该接口不会生成可执行 step。",
            "resolution": "如需覆盖，请调整 Campaign 范围或动作策略后重新生成计划。",
        }

    def _review_item_from_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target_type": "api_candidate",
            "target_id": str(candidate.get("id")),
            "policy": str(candidate.get("policy")),
            "title": f"确认是否生成 {candidate.get('method')} {candidate.get('path')} 资产草稿",
            "reason": str(candidate.get("risk_reason") or "该步骤需要人工确认"),
            "if_approved": "生成 API Case IR v2 draft，但 Phase 1 不执行",
            "if_rejected": "跳过该候选接口，只保留计划和风险说明",
            "available_choices": ["skip", "generate_asset_only", "approve_for_future_execution"],
        }

    def _review_item_from_ui_step(self, flow: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target_type": "ui_step",
            "target_id": str(step.get("id")),
            "policy": str(step.get("policy") or "confirmation_required"),
            "title": f"确认 UI 步骤：{step.get('description') or step.get('action')}",
            "reason": "该 UI 步骤需要人工确认",
            "if_approved": "生成 Visual UI draft，但 Phase 1 不执行",
            "if_rejected": f"跳过 {flow.get('name')} 中的该步骤",
            "available_choices": ["skip", "generate_asset_only", "approve_for_future_execution"],
        }

    def _build_api_ir_step(
        self,
        candidate: Dict[str, Any],
        campaign: ScanCampaign,
        plan: ScanCampaignPlan,
        review_item: Optional[ScanCampaignReviewItem],
    ) -> Dict[str, Any]:
        assertion = self._assertion_from_recommendations(candidate.get("recommended_assertions") or [])
        metadata = {
            "source_type": "scan_campaign",
            "campaign_id": campaign.id,
            "plan_id": plan.id,
            "candidate_id": candidate.get("id"),
            "candidate_source": candidate.get("source"),
            "source_ref": candidate.get("source_ref") or {},
            "policy": candidate.get("policy"),
            "risk_level": candidate.get("risk_level"),
            "risk_reason": candidate.get("risk_reason"),
            "conditions": candidate.get("conditions") or [],
            "review_choice": self._enum_value(review_item.choice) if review_item else None,
            "execution_allowed_in_phase": False,
        }
        step = {
            "id": f"STEP_{candidate.get('id')}",
            "name": candidate.get("natural_language_step") or f"{candidate.get('method')} {candidate.get('path')}",
            "description": "由 Scan Campaign Phase 1 生成的 API 资产草稿",
            "step_type": "API",
            "request": {
                "method": candidate.get("method") or "GET",
                "url": candidate.get("path") or "/",
                "path": candidate.get("path") or "/",
                "headers": {},
                "query_params": {},
                "path_params": {},
                "body": {},
                "timeout_ms": 30000,
                "content_type": "application/json",
            },
            "assertion": assertion,
            "extraction": candidate.get("recommended_extractions") or {},
            "metadata": metadata,
        }
        return normalize_api_step_v2(step, "API")

    def _build_visual_ui_case(self, flow: Dict[str, Any], campaign: ScanCampaign, plan: ScanCampaignPlan) -> Dict[str, Any]:
        metadata = {
            "source_type": "scan_campaign",
            "campaign_id": campaign.id,
            "plan_id": plan.id,
            "flow_id": flow.get("id"),
            "policy": flow.get("policy") or "allowed",
            "risk_level": flow.get("risk_level"),
            "execution_allowed_in_phase": False,
        }
        steps = []
        for index, step in enumerate(flow.get("steps") or []):
            steps.append(
                {
                    "id": step.get("id") or f"UI_STEP_{index + 1}",
                    "step_index": index,
                    "action": step.get("action"),
                    "target_description": step.get("description") or step.get("target"),
                    "value": step.get("target") if step.get("action") == "GOTO" else None,
                    "metadata": {
                        "campaign_id": campaign.id,
                        "plan_id": plan.id,
                        "flow_id": flow.get("id"),
                        "policy": step.get("policy") or "allowed",
                        "risk_level": step.get("risk_level") or "low",
                        "requires_confirmation": bool(step.get("requires_confirmation")),
                        "execution_allowed_in_phase": False,
                    },
                }
            )
        return {
            "name": flow.get("name") or "Scan Campaign UI Draft",
            "description": "由 Scan Campaign Phase 1 生成的 Visual UI 资产草稿",
            "base_url": (campaign.target or {}).get("base_url"),
            "steps": steps,
            "expected_results": flow.get("assertions") or [],
            "metadata": metadata,
        }

    def _can_generate_candidate(
        self,
        candidate: Dict[str, Any],
        review_by_target: Dict[str, ScanCampaignReviewItem],
        include_only_approved: bool,
    ) -> bool:
        policy = candidate.get("policy")
        if policy in {"forbidden", "out_of_scope"}:
            return False
        if policy == "allowed":
            return True
        review = review_by_target.get(str(candidate.get("id")))
        if review is None:
            return False
        choice = self._enum_value(review.choice)
        if choice == "skip" or choice == "pending":
            return False
        return choice in {"generate_asset_only", "approve_for_future_execution"} or not include_only_approved

    def _can_generate_flow(
        self,
        flow: Dict[str, Any],
        review_by_target: Dict[str, ScanCampaignReviewItem],
        include_only_approved: bool,
    ) -> bool:
        for step in flow.get("steps") or []:
            if not step.get("requires_confirmation"):
                continue
            review = review_by_target.get(str(step.get("id")))
            if review is None:
                return False
            choice = self._enum_value(review.choice)
            if include_only_approved and choice not in {"generate_asset_only", "approve_for_future_execution"}:
                return False
        return True

    def _asset_draft_model(self, **kwargs) -> ScanCampaignAssetDraft:
        return ScanCampaignAssetDraft(id=self._new_id("DRAFT"), **kwargs)

    def _skipped_item(self, candidate: Dict[str, Any], reason: str) -> Dict[str, Any]:
        return {
            "target": f"{candidate.get('method')} {candidate.get('path')}",
            "candidate_id": candidate.get("id"),
            "policy": candidate.get("policy"),
            "reason": reason,
        }

    def _build_summary(self, campaign: ScanCampaign, api_candidates: list[dict], risk_items: list[dict]) -> Dict[str, Any]:
        strategy = campaign.strategy or {}
        return {
            "title": f"{campaign.name} 计划",
            "scan_mode": strategy.get("scan_mode") or "graybox",
            "intensity": strategy.get("intensity") or "smoke",
            "risk_level": "medium" if risk_items else "low",
            "execution_state": "not_executed",
        }

    def _build_scope_review(self, campaign: ScanCampaign, risk_items: list[dict]) -> Dict[str, Any]:
        target = campaign.target or {}
        boundaries = campaign.boundaries or {}
        return {
            "included": self._split_scope_text(target.get("scope_text")),
            "excluded": self._split_scope_text(target.get("out_of_scope_text")),
            "allowed_domains": self._string_list(boundaries.get("allowed_domains")),
            "allowed_paths": self._string_list(boundaries.get("allowed_paths")),
            "blocked_out_of_scope": [
                {"target": item.get("target"), "reason": item.get("reason")}
                for item in risk_items
                if item.get("policy") in {"forbidden", "out_of_scope"}
            ],
        }

    def _build_coverage_summary(self, ui_flows: list[dict], api_candidates: list[dict], risk_items: list[dict]) -> Dict[str, Any]:
        return {
            "planned_modules": 1,
            "ui_flow_count": len(ui_flows),
            "api_candidate_count": len(api_candidates),
            "blocked_count": len([item for item in risk_items if item.get("policy") in {"forbidden", "out_of_scope"}]),
            "confirmation_required_count": len([item for item in api_candidates if item.get("policy") == "confirmation_required"]),
            "conditional_allowed_count": len([item for item in api_candidates if item.get("policy") == "conditional_allowed"]),
        }

    def _conditions_for_candidate(self, candidate: Dict[str, Any], campaign: ScanCampaign) -> List[Dict[str, Any]]:
        data_policy = campaign.data_policy or {}
        return [
            {
                "name": "环境非生产",
                "status": "failed" if data_policy.get("environment_safety") == "production-readonly" else "passed",
                "detail": data_policy.get("environment_safety") or "staging",
            },
            {
                "name": "测试数据标识存在",
                "status": "passed" if data_policy.get("test_data_markers") else "pending",
                "detail": data_policy.get("test_data_markers") or [],
            },
            {
                "name": "清理策略存在",
                "status": "passed" if data_policy.get("cleanup_policy") else "pending",
                "detail": data_policy.get("cleanup_policy") or "未配置",
            },
        ]

    def _asset_draft_summary(self, drafts: List[ScanCampaignAssetDraft]) -> Dict[str, Any]:
        return {
            "api_case_ir_steps": [draft.draft_payload for draft in drafts if draft.asset_type == "api_case_ir_step"],
            "visual_ui_steps": [draft.draft_payload for draft in drafts if draft.asset_type == "visual_ui_case"],
        }

    def _campaign_to_payload(self, campaign: ScanCampaign) -> Dict[str, Any]:
        return {
            "id": campaign.id,
            "name": campaign.name,
            "target": campaign.target,
            "strategy": campaign.strategy,
            "boundaries": campaign.boundaries,
            "action_policy": campaign.action_policy,
            "data_policy": campaign.data_policy,
            "special_limits": campaign.special_limits,
            "status": campaign.status,
            "ai_plan_id": campaign.ai_plan_id,
            "created_at": campaign.created_at,
        }

    def _campaign_snapshot(self, campaign: ScanCampaign) -> Dict[str, Any]:
        return {
            "id": campaign.id,
            "name": campaign.name,
            "target": campaign.target or {},
            "strategy": campaign.strategy or {},
            "boundaries": campaign.boundaries or {},
            "action_policy": campaign.action_policy or {},
            "data_policy": campaign.data_policy or {},
            "special_limits": campaign.special_limits or {},
        }

    async def _next_plan_version(self, campaign_id: str) -> int:
        result = await self.db.execute(
            select(func.max(ScanCampaignPlan.version)).where(ScanCampaignPlan.campaign_id == campaign_id)
        )
        return int(result.scalar() or 0) + 1

    def _build_search_text(self, payload: Dict[str, Any]) -> str:
        target = payload.get("target") or {}
        strategy = payload.get("strategy") or {}
        parts = [
            payload.get("name") or "",
            target.get("business_module") or "",
            target.get("scope_text") or "",
            target.get("out_of_scope_text") or "",
            f"scan_mode:{strategy.get('scan_mode') or 'graybox'}",
        ]
        return "\n".join(str(part).lower() for part in parts if part)

    def _is_path_allowed(self, path: str, allowed_paths: List[str]) -> bool:
        return any(path == allowed or path.startswith(f"{allowed.rstrip('/')}/") for allowed in allowed_paths)

    def _string_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    def _split_scope_text(self, value: Any) -> List[str]:
        text = str(value or "").strip()
        if not text:
            return []
        separators = ["，", ",", "、", "\n"]
        for separator in separators[1:]:
            text = text.replace(separator, separators[0])
        return [part.strip() for part in text.split(separators[0]) if part.strip()]

    def _assertion_from_recommendations(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        status_code = 200
        json_assertions: dict[str, Any] = {}
        for item in recommendations:
            if item.get("type") == "status_code":
                status_code = int(item.get("expected") or status_code)
            if item.get("type") == "json_path" and item.get("path"):
                json_assertions[str(item["path"])] = item.get("expected")
        return {"status_code": status_code, "json_assertions": json_assertions}

    def _default_status_code(self, responses: Any) -> int:
        if not isinstance(responses, dict) or not responses:
            return 200
        for status_code in ("200", "201", "204"):
            if status_code in responses:
                return int(status_code)
        for status_code in responses:
            if str(status_code).isdigit():
                return int(status_code)
        return 200

    def _enum_value(self, value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)
