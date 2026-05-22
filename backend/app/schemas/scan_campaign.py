"""Pydantic schemas for Scan Campaign Phase 1 APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScanCampaignCreate(BaseModel):
    name: str = Field(..., max_length=200)
    target: Dict[str, Any] = Field(default_factory=dict)
    strategy: Dict[str, Any] = Field(default_factory=dict)
    boundaries: Dict[str, Any] = Field(default_factory=dict)
    action_policy: Dict[str, Any] = Field(default_factory=dict)
    data_policy: Dict[str, Any] = Field(default_factory=dict)
    special_limits: Dict[str, Any] = Field(default_factory=dict)


class ScanCampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    target: Optional[Dict[str, Any]] = None
    strategy: Optional[Dict[str, Any]] = None
    boundaries: Optional[Dict[str, Any]] = None
    action_policy: Optional[Dict[str, Any]] = None
    data_policy: Optional[Dict[str, Any]] = None
    special_limits: Optional[Dict[str, Any]] = None


class ScanCampaignResponse(BaseModel):
    id: str
    name: str
    status: str
    target: Dict[str, Any]
    strategy: Dict[str, Any]
    boundaries: Dict[str, Any]
    action_policy: Dict[str, Any]
    data_policy: Dict[str, Any]
    special_limits: Dict[str, Any]
    ai_plan_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class ScanCampaignListResponse(BaseModel):
    items: List[ScanCampaignResponse]
    total: int
    page: int
    page_size: int


class GeneratePlanRequest(BaseModel):
    regenerate: bool = False
    notes: Optional[str] = None


class ReviewItemResponse(BaseModel):
    id: str
    campaign_id: str
    plan_id: str
    target_type: str
    target_id: str
    policy: str
    title: str
    reason: str
    if_approved: str
    if_rejected: str
    available_choices: List[str]
    choice: str
    comment: Optional[str]
    choice_updated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ScanCampaignPlanResponse(BaseModel):
    plan_id: str
    campaign_draft_id: str
    version: int
    status: str
    summary: Dict[str, Any]
    scope_review: Dict[str, Any]
    ui_flows: List[Dict[str, Any]]
    api_candidates: List[Dict[str, Any]]
    risk_items: List[Dict[str, Any]]
    manual_review_items: List[ReviewItemResponse]
    asset_drafts: Dict[str, Any]
    coverage_summary: Dict[str, Any]
    generation_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ReviewItemUpdate(BaseModel):
    choice: str
    comment: Optional[str] = None


class ReviewItemUpdateResponse(BaseModel):
    item: ReviewItemResponse
    plan_status: str


class GenerateAssetDraftsRequest(BaseModel):
    asset_types: List[str] = Field(default_factory=lambda: ["api_case_ir", "visual_ui_case"])
    include_only_approved: bool = True


class AssetDraftResponse(BaseModel):
    id: str
    campaign_id: str
    plan_id: str
    asset_type: str
    source_type: str
    source_item_id: str
    policy: str
    risk_level: Optional[str]
    draft_payload: Dict[str, Any]
    metadata: Dict[str, Any]
    skipped_reason: Optional[str]
    created_at: datetime


class GenerateAssetDraftsResponse(BaseModel):
    api_case_ir_steps: List[Dict[str, Any]]
    visual_ui_cases: List[Dict[str, Any]]
    skipped_items: List[Dict[str, Any]]
    asset_drafts: List[AssetDraftResponse]
