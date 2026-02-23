import uuid
from datetime import datetime
import enum
from typing import List, Optional

from sqlalchemy import Column, String, Integer, Text, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class VisualUseCaseStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class VisualStepAction(str, enum.Enum):
    GOTO = "GOTO"
    CLICK = "CLICK"
    TYPE = "TYPE"
    WAIT = "WAIT"
    ASSERT = "ASSERT"
    SCROLL = "SCROLL"


class VisualUseCase(Base):
    """
    视觉UI自动化测试用例
    """
    __tablename__ = "visual_use_cases"

    id = Column(String(50), primary_key=True, default=lambda: f"vuc-{uuid.uuid4().hex[:8]}", index=True)
    project_id = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(VisualUseCaseStatus), default=VisualUseCaseStatus.draft, nullable=False)
    base_url = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联步骤 (一对多)
    # cascade="all, delete-orphan" 确保删除用例时，关联的步骤也会被删除
    steps = relationship("VisualStep", back_populates="use_case", cascade="all, delete-orphan", order_by="VisualStep.step_index")


class VisualStep(Base):
    """
    视觉UI自动化测试步骤
    """
    __tablename__ = "visual_steps"

    id = Column(String(50), primary_key=True, default=lambda: f"vst-{uuid.uuid4().hex[:8]}", index=True)
    case_id = Column(String(50), ForeignKey("visual_use_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    
    step_index = Column(Integer, nullable=False)
    action = Column(Enum(VisualStepAction), nullable=False)
    target_description = Column(Text, nullable=True)  # 例如 "登录按钮" (GOTO/WAIT等可能为空或特殊用法)
    value = Column(String(500), nullable=True)        # 输入值，断言值，或 GOTO的URL
    screenshot_baseline = Column(String(1000), nullable=True) # VRT 基线存储路径
    
    # 关联回 Case
    use_case = relationship("VisualUseCase", back_populates="steps")
