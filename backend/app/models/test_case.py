"""
测试用例模型 (TC-IR 持久化)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import String, Text, JSON, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import Base


class ExecutionMode(str, enum.Enum):
    """执行模式"""
    UI = "UI"
    API = "API"
    HYBRID = "HYBRID"


class Priority(str, enum.Enum):
    """优先级"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TCStatus(str, enum.Enum):
    """用例状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TestCase(Base):
    """
    测试用例模型
    
    对应 TC-IR (Test Case Intermediate Representation)
    """
    __tablename__ = "test_cases"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 执行配置
    mode: Mapped[ExecutionMode] = mapped_column(
        Enum(ExecutionMode), default=ExecutionMode.UI
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority), default=Priority.P1
    )
    status: Mapped[TCStatus] = mapped_column(
        Enum(TCStatus), default=TCStatus.DRAFT
    )
    
    # 步骤定义 (JSON 存储)
    steps: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # 元数据
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    dependencies: Mapped[List[str]] = mapped_column(JSON, default=list)
    variables: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # 来源追溯
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    
    def to_tcir(self) -> Dict[str, Any]:
        """转换为 TC-IR 格式"""
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
