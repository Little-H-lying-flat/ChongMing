"""Scan Campaign Phase 1 endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.scan_campaign import (
    AssetDraftListResponse,
    AssetDraftResponse,
    AssetPromotionListResponse,
    AssetPromotionResponse,
    ConfirmScanCampaignExecutionRequest,
    ConfirmScanCampaignExecutionResponse,
    GenerateAssetDraftsRequest,
    GenerateAssetDraftsResponse,
    GeneratePlanRequest,
    PromoteAssetDraftResult,
    PromoteAssetDraftsRequest,
    PromoteAssetDraftsResponse,
    ReviewItemUpdate,
    ReviewItemUpdateResponse,
    ScanCampaignCreate,
    ScanCampaignListResponse,
    ScanCampaignPlanResponse,
    ScanCampaignResponse,
    ScanCampaignUpdate,
    SmartScanExecutionSummaryResponse,
    SmartScanReportResponse,
)
from app.api.v1.endpoints.executions import ExecutionRequest, create_and_dispatch_execution
from app.services.scan_campaign_service import (
    ScanCampaignConflictError,
    ScanCampaignNotFoundError,
    ScanCampaignService,
    ScanCampaignValidationError,
)

router = APIRouter()


def _service(db: AsyncSession) -> ScanCampaignService:
    return ScanCampaignService(db)


@router.post("", response_model=ScanCampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_scan_campaign(payload: ScanCampaignCreate, db: AsyncSession = Depends(get_db)):
    service = _service(db)
    try:
        campaign = await service.create(payload.model_dump())
    except ScanCampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return service.campaign_to_response(campaign)


@router.get("", response_model=ScanCampaignListResponse)
async def list_scan_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    scan_mode: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        items = await service.list(
            page=page,
            page_size=page_size,
            status=status,
            keyword=keyword,
            scan_mode=scan_mode,
        )
        total = await service.count(status=status, keyword=keyword, scan_mode=scan_mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ScanCampaignListResponse(
        items=[ScanCampaignResponse(**service.campaign_to_response(item)) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{campaign_id}", response_model=ScanCampaignResponse)
async def get_scan_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    service = _service(db)
    campaign = await service.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return service.campaign_to_response(campaign)


@router.put("/{campaign_id}", response_model=ScanCampaignResponse)
async def update_scan_campaign(
    campaign_id: str,
    payload: ScanCampaignUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        campaign = await service.update(campaign_id, payload.model_dump(exclude_unset=True))
    except ScanCampaignConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ScanCampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return service.campaign_to_response(campaign)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    service = _service(db)
    deleted = await service.delete(campaign_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return None


@router.post("/{campaign_id}/generate-plan", response_model=ScanCampaignPlanResponse)
async def generate_scan_campaign_plan(
    campaign_id: str,
    payload: GeneratePlanRequest,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        plan = await service.generate_plan(
            campaign_id,
            regenerate=payload.regenerate,
            notes=payload.notes,
        )
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScanCampaignConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ScanCampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    review_items = await service.list_review_items(plan.id)
    asset_drafts = await service.list_asset_drafts(plan.id)
    return service.build_plan_response(plan, review_items, asset_drafts)


@router.get("/{campaign_id}/plan", response_model=ScanCampaignPlanResponse)
async def get_latest_scan_campaign_plan(campaign_id: str, db: AsyncSession = Depends(get_db)):
    service = _service(db)
    plan = await service.get_latest_plan(campaign_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Latest plan for Campaign {campaign_id} not found")
    review_items = await service.list_review_items(plan.id)
    asset_drafts = await service.list_asset_drafts(plan.id)
    return service.build_plan_response(plan, review_items, asset_drafts)


@router.get("/{campaign_id}/plans/{plan_id}", response_model=ScanCampaignPlanResponse)
async def get_scan_campaign_plan(campaign_id: str, plan_id: str, db: AsyncSession = Depends(get_db)):
    service = _service(db)
    plan = await service.get_plan(campaign_id, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    review_items = await service.list_review_items(plan.id)
    asset_drafts = await service.list_asset_drafts(plan.id)
    return service.build_plan_response(plan, review_items, asset_drafts)


@router.patch(
    "/{campaign_id}/plans/{plan_id}/review-items/{review_item_id}",
    response_model=ReviewItemUpdateResponse,
)
async def update_scan_campaign_review_item(
    campaign_id: str,
    plan_id: str,
    review_item_id: str,
    payload: ReviewItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        item, plan_status = await service.update_review_item(
            campaign_id,
            plan_id,
            review_item_id,
            payload.choice,
            payload.comment,
        )
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScanCampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ReviewItemUpdateResponse(
        item=service.review_item_to_response(item),
        plan_status=plan_status,
    )


@router.get(
    "/{campaign_id}/plans/{plan_id}/asset-drafts",
    response_model=AssetDraftListResponse,
)
async def list_scan_campaign_asset_drafts(
    campaign_id: str,
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        drafts = await service.list_asset_drafts_for_plan(campaign_id, plan_id)
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return AssetDraftListResponse(
        items=[AssetDraftResponse(**service.asset_draft_to_response(draft)) for draft in drafts]
    )


@router.get(
    "/{campaign_id}/plans/{plan_id}/asset-drafts/promotions",
    response_model=AssetPromotionListResponse,
)
async def list_scan_campaign_asset_promotions(
    campaign_id: str,
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        promotions = await service.list_asset_promotions(campaign_id, plan_id)
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return AssetPromotionListResponse(
        items=[AssetPromotionResponse(**service.asset_promotion_to_response(item)) for item in promotions]
    )


@router.post(
    "/{campaign_id}/plans/{plan_id}/promote-asset-drafts",
    response_model=PromoteAssetDraftsResponse,
)
async def promote_scan_campaign_asset_drafts(
    campaign_id: str,
    plan_id: str,
    payload: PromoteAssetDraftsRequest,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        result = await service.promote_asset_drafts(
            campaign_id,
            plan_id,
            draft_ids=payload.draft_ids,
            confirmation=payload.confirmation,
            allow_duplicates=payload.allow_duplicates,
            visual_project_id=payload.visual_project_id,
        )
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScanCampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return PromoteAssetDraftsResponse(
        promoted=[PromoteAssetDraftResult(**item) for item in result["promoted"]],
        duplicates=[PromoteAssetDraftResult(**item) for item in result["duplicates"]],
        skipped=[PromoteAssetDraftResult(**item) for item in result["skipped"]],
        failed=[PromoteAssetDraftResult(**item) for item in result["failed"]],
        execution_created=bool(result["execution_created"]),
    )


@router.get(
    "/{campaign_id}/plans/{plan_id}/execution-summary",
    response_model=SmartScanExecutionSummaryResponse,
)
async def get_scan_campaign_execution_summary(
    campaign_id: str,
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        return SmartScanExecutionSummaryResponse(**await service.get_execution_summary(campaign_id, plan_id))
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/{campaign_id}/plans/{plan_id}/report",
    response_model=SmartScanReportResponse,
)
async def get_scan_campaign_report(
    campaign_id: str,
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        return SmartScanReportResponse(**await service.build_smart_scan_report(campaign_id, plan_id))
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{campaign_id}/plans/{plan_id}/confirm-execution",
    response_model=ConfirmScanCampaignExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def confirm_scan_campaign_execution(
    campaign_id: str,
    plan_id: str,
    payload: ConfirmScanCampaignExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        prepared = await service.build_phase3_execution_payload(
            campaign_id,
            plan_id,
            promotion_ids=payload.promotion_ids,
            confirmation=payload.confirmation,
            mode=payload.mode,
            engine=payload.engine,
            parallel=payload.parallel,
            max_workers=payload.max_workers,
            env=payload.env,
        )
        execution = await create_and_dispatch_execution(
            ExecutionRequest(
                tc_ids=prepared["tc_ids"],
                mode=payload.mode,
                engine=payload.engine,
                parallel=payload.parallel,
                max_workers=payload.max_workers,
                env=payload.env,
                dynamic_payload=prepared["dynamic_payload"],
            ),
            background_tasks,
            db,
            config_overrides=prepared["config_overrides"],
        )
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScanCampaignConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ScanCampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ConfirmScanCampaignExecutionResponse(
        execution_created=True,
        execution_id=execution.execution_id,
        status=execution.status,
        total_cases=execution.total_cases,
        dashboard_url=execution.dashboard_url,
        selected_promotions=prepared["selected_promotions"],
        tc_ids=prepared["tc_ids"],
        dynamic_payload_count=len(prepared["dynamic_payload"]),
        skipped=prepared["skipped"],
    )


@router.post(
    "/{campaign_id}/plans/{plan_id}/generate-asset-drafts",
    response_model=GenerateAssetDraftsResponse,
)
async def generate_scan_campaign_asset_drafts(
    campaign_id: str,
    plan_id: str,
    payload: GenerateAssetDraftsRequest,
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        result = await service.generate_asset_drafts(
            campaign_id,
            plan_id,
            asset_types=payload.asset_types,
            include_only_approved=payload.include_only_approved,
        )
    except ScanCampaignNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScanCampaignValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return GenerateAssetDraftsResponse(
        api_case_ir_steps=result["api_case_ir_steps"],
        visual_ui_cases=result["visual_ui_cases"],
        skipped_items=result["skipped_items"],
        asset_drafts=[
            AssetDraftResponse(**service.asset_draft_to_response(draft))
            for draft in result["asset_drafts"]
        ],
    )
