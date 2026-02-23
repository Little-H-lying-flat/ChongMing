from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.visual_ui import VisualUseCaseStatus, VisualStepAction

# === Visual Step Schemas ===

class VisualStepBase(BaseModel):
    step_index: int = Field(..., description="步骤执行顺序", json_schema_extra={"example": 1})
    action: VisualStepAction = Field(..., description="动作为 GOTO, CLICK, TYPE, WAIT, ASSERT, SCROLL 之一")
    target_description: Optional[str] = Field(None, description="操作目标元素的自然语言描述", json_schema_extra={"example": "右下角灰色的登录按钮"})
    value: Optional[str] = Field(None, description="输入值或URL目标", json_schema_extra={"example": "https://saucedemo.com"})
    screenshot_baseline: Optional[str] = Field(None, description="视觉基线图片的路径URL")

class VisualStepCreate(VisualStepBase):
    pass

class VisualStepUpdate(BaseModel):
    step_index: Optional[int] = None
    action: Optional[VisualStepAction] = None
    target_description: Optional[str] = None
    value: Optional[str] = None
    screenshot_baseline: Optional[str] = None

class VisualStepResponse(VisualStepBase):
    id: str
    case_id: str

    model_config = {"from_attributes": True}

# === Visual Use Case Schemas ===

class VisualUseCaseBase(BaseModel):
    project_id: str = Field(..., description="项目ID")
    name: str = Field(..., description="用例名称")
    description: Optional[str] = Field(None, description="用例描述")
    status: Optional[VisualUseCaseStatus] = Field(VisualUseCaseStatus.draft, description="用例状态")
    base_url: Optional[str] = Field(None, description="关联的默认环境变量 Base URL")

class VisualUseCaseCreate(VisualUseCaseBase):
    steps: List[VisualStepCreate] = Field(default_factory=list, description="用例步骤列表")

class VisualUseCaseUpdate(BaseModel):
    project_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[VisualUseCaseStatus] = None
    base_url: Optional[str] = None
    steps: Optional[List[VisualStepCreate]] = Field(None, description="全量覆盖：提供新的步骤列表，会删除旧步骤")

class VisualUseCaseResponse(VisualUseCaseBase):
    id: str
    created_at: datetime
    updated_at: datetime
    steps: List[VisualStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
