"""
脚本模型 (凤凰涅槃层产物)
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Text, JSON, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import Base


class CompilationStrategy(str, enum.Enum):
    """编译策略"""
    EXACT = "exact"
    OPTIMIZED = "optimized"
    DATA_DRIVEN = "data_driven"
    HYBRID = "hybrid"


class Script(Base):
    """
    脚本模型
    
    凤凰涅槃层编译产物的元数据
    """
    __tablename__ = "scripts"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # 来源
    source_tc_id: Mapped[str] = mapped_column(String(50))
    source_trace_id: Mapped[str] = mapped_column(String(50))
    
    # 文件信息
    file_path: Mapped[str] = mapped_column(String(500))
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # 编译信息
    strategy: Mapped[CompilationStrategy] = mapped_column(
        Enum(CompilationStrategy), default=CompilationStrategy.OPTIMIZED
    )
    
    # 参数
    parameters: Mapped[List[str]] = mapped_column(JSON, default=list)
    step_count: Mapped[int] = mapped_column(default=0)
    
    # Git 信息
    git_commit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    git_branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
