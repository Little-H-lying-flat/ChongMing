"""Test case model (TC-IR persistence)."""

from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExecutionMode(str, enum.Enum):
    UI = "UI"
    API = "API"
    HYBRID = "HYBRID"


class Priority(str, enum.Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TCStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    ACTIVE = "active"
    FROZEN = "frozen"
    DISABLED = "disabled"
    ARCHIVED = "archived"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    mode: Mapped[ExecutionMode] = mapped_column(Enum(ExecutionMode), default=ExecutionMode.UI)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.P1)
    status: Mapped[TCStatus] = mapped_column(Enum(TCStatus), default=TCStatus.DRAFT)

    steps: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    dependencies: Mapped[List[str]] = mapped_column(JSON, default=list)
    variables: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )

    def to_tcir(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "mode": self.mode.value,
            "priority": self.priority.value,
            "steps": self.steps,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "variables": self.variables,
        }
