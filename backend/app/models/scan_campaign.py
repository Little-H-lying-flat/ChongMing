"""Scan Campaign Phase 1 persistence models."""

from __future__ import annotations

from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScanCampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    PLAN_GENERATED = "plan_generated"
    NEEDS_REVISION = "needs_revision"
    ARCHIVED = "archived"


class ScanCampaignPlanStatus(str, enum.Enum):
    GENERATED = "generated"
    REVIEW_SAVED = "review_saved"
    ASSET_DRAFTS_GENERATED = "asset_drafts_generated"
    SUPERSEDED = "superseded"


class ScanCampaignReviewChoice(str, enum.Enum):
    PENDING = "pending"
    SKIP = "skip"
    GENERATE_ASSET_ONLY = "generate_asset_only"
    APPROVE_FOR_FUTURE_EXECUTION = "approve_for_future_execution"


class ScanCampaign(Base):
    __tablename__ = "scan_campaigns"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[ScanCampaignStatus] = mapped_column(
        Enum(ScanCampaignStatus), default=ScanCampaignStatus.DRAFT, index=True
    )

    target: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    strategy: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    boundaries: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    action_policy: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    data_policy: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    special_limits: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    ai_plan_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    search_text: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    plans: Mapped[List["ScanCampaignPlan"]] = relationship(
        "ScanCampaignPlan", back_populates="campaign", cascade="all, delete-orphan"
    )
    review_items: Mapped[List["ScanCampaignReviewItem"]] = relationship(
        "ScanCampaignReviewItem", back_populates="campaign", cascade="all, delete-orphan"
    )
    asset_drafts: Mapped[List["ScanCampaignAssetDraft"]] = relationship(
        "ScanCampaignAssetDraft", back_populates="campaign", cascade="all, delete-orphan"
    )


class ScanCampaignPlan(Base):
    __tablename__ = "scan_campaign_plans"
    __table_args__ = (UniqueConstraint("campaign_id", "version", name="uq_scan_campaign_plan_version"),)

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaigns.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ScanCampaignPlanStatus] = mapped_column(
        Enum(ScanCampaignPlanStatus), default=ScanCampaignPlanStatus.GENERATED, index=True
    )

    summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    scope_review: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    ui_flows: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    api_candidates: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    risk_items: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    coverage_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    generation_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    campaign: Mapped["ScanCampaign"] = relationship("ScanCampaign", back_populates="plans")
    review_items: Mapped[List["ScanCampaignReviewItem"]] = relationship(
        "ScanCampaignReviewItem", back_populates="plan", cascade="all, delete-orphan"
    )
    asset_drafts: Mapped[List["ScanCampaignAssetDraft"]] = relationship(
        "ScanCampaignAssetDraft", back_populates="plan", cascade="all, delete-orphan"
    )


class ScanCampaignReviewItem(Base):
    __tablename__ = "scan_campaign_review_items"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaigns.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaign_plans.id", ondelete="CASCADE"), index=True
    )

    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    if_approved: Mapped[str] = mapped_column(Text, nullable=False)
    if_rejected: Mapped[str] = mapped_column(Text, nullable=False)
    available_choices: Mapped[List[str]] = mapped_column(JSON, default=list)
    choice: Mapped[ScanCampaignReviewChoice] = mapped_column(
        Enum(ScanCampaignReviewChoice), default=ScanCampaignReviewChoice.PENDING
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    choice_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    campaign: Mapped["ScanCampaign"] = relationship("ScanCampaign", back_populates="review_items")
    plan: Mapped["ScanCampaignPlan"] = relationship("ScanCampaignPlan", back_populates="review_items")


class ScanCampaignAssetDraft(Base):
    __tablename__ = "scan_campaign_asset_drafts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaigns.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaign_plans.id", ondelete="CASCADE"), index=True
    )

    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    draft_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    draft_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    skipped_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    campaign: Mapped["ScanCampaign"] = relationship("ScanCampaign", back_populates="asset_drafts")
    plan: Mapped["ScanCampaignPlan"] = relationship("ScanCampaignPlan", back_populates="asset_drafts")
    promotions: Mapped[List["ScanCampaignAssetPromotion"]] = relationship(
        "ScanCampaignAssetPromotion", back_populates="asset_draft", cascade="all, delete-orphan"
    )


class ScanCampaignAssetPromotion(Base):
    __tablename__ = "scan_campaign_asset_promotions"
    __table_args__ = (
        UniqueConstraint("asset_draft_id", "generated_asset_type", name="uq_scan_campaign_asset_promotion"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaigns.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaign_plans.id", ondelete="CASCADE"), index=True
    )
    asset_draft_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("scan_campaign_asset_drafts.id", ondelete="CASCADE"), index=True
    )

    draft_type: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_asset_id: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="created", index=True)
    promotion_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    asset_draft: Mapped["ScanCampaignAssetDraft"] = relationship("ScanCampaignAssetDraft", back_populates="promotions")
