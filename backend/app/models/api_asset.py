"""API asset persistence model."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApiAsset(Base):
    __tablename__ = "api_assets"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    asset_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)

    source_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    spec_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    spec_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    parameters: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    request_body: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    responses: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    security: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    search_text: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )
