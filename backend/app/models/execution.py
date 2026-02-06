"""
执行记录模型
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Text, JSON, DateTime, Float, Integer, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import Base


class ExecutionStatus(str, enum.Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    ERROR = "error"


class Execution(Base):
    """
    执行记录模型
    
    记录一次测试执行的完整信息
    """
    __tablename__ = "executions"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    
    # 执行配置
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # 状态
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.PENDING
    )
    
    # 统计
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0)
    skipped_cases: Mapped[int] = mapped_column(Integer, default=0)
    
    # 时间
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    
    # 报告
    report_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # 关联
    steps: Mapped[List["ExecutionStep"]] = relationship(
        "ExecutionStep", back_populates="execution"
    )


class ExecutionStep(Base):
    """
    执行步骤记录
    
    记录每个用例的执行结果
    """
    __tablename__ = "execution_steps"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("executions.id")
    )
    tc_id: Mapped[str] = mapped_column(String(50))
    
    # 状态
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.PENDING
    )
    
    # 结果
    trace_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    step_results: Mapped[dict] = mapped_column(JSON, default=list)
    
    # 时间
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    
    # 截图
    screenshots: Mapped[List[str]] = mapped_column(JSON, default=list)
    
    # 关联
    execution: Mapped["Execution"] = relationship(
        "Execution", back_populates="steps"
    )
