"""
测试数据记录模型

对应 Issue #DF-002: 数据清理
用于追踪生成的测试数据，支持自动清理
"""

from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import String, Text, JSON, DateTime, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DataStatus(str, enum.Enum):
    """数据状态"""
    ACTIVE = "active"
    EXPIRED = "expired"
    CLEANED = "cleaned"


class DataRecord(Base):
    """
    测试数据记录
    
    用于追踪通过数据工厂生成的测试数据
    """
    __tablename__ = "data_records"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    
    # 数据标识
    schema_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    # 生成的数据内容
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    count: Mapped[int] = mapped_column(Integer, default=1)
    
    # 状态与清理
    status: Mapped[DataStatus] = mapped_column(
        Enum(DataStatus), default=DataStatus.ACTIVE
    )
    ttl_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 关联信息
    execution_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    environment_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # 商业化预留
    tenant_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cleaned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
