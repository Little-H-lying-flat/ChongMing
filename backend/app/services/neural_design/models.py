from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum

class DesignRequest(BaseModel):
    """
    设计请求
    
    接收用户的自然语言需求或 PRD
    """
    project_id: str = Field(..., description="项目 ID")
    requirement_text: str = Field(..., description="需求描述或 PRD 文本")
    context: Optional[str] = Field(None, description="上下文信息 (如相关 API 定义)")

class DraftStep(BaseModel):
    """
    草稿步骤
    
    LLM 初步生成的测试步骤
    """
    step_id: str = Field(..., description="步骤 ID")
    intent: str = Field(..., description="测试意图")
    method: str = Field(..., description="HTTP 方法")
    url_path: str = Field(..., description="URL 路径")
    description: str = Field(..., description="步骤描述")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据示例")
    expected_outcome: Optional[str] = Field(None, description="预期结果描述")

class DraftTestCase(BaseModel):
    """
    草稿测试用例
    
    LLM 生成的非结构化测试用例
    """
    case_name: str = Field(..., description="用例名称")
    description: str = Field(..., description="用例描述")
    steps: List[DraftStep] = Field(..., description="测试步骤列表")
    tags: List[str] = Field(default_factory=list, description="标签")

class RefinedRequestSpec(BaseModel):
    """请求规范 (Pydantic版)"""
    method: str
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    query_params: Dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = 30000

class RefinedAssertionSpec(BaseModel):
    """断言规范 (Pydantic版)"""
    status_code: Optional[int] = None
    schema_validate: bool = False
    json_assertions: Dict[str, Any] = Field(default_factory=dict)
    contains: Optional[str] = None
    expression: Optional[str] = None

class RefinedTestStep(BaseModel):
    """
    Refined Test Step
    
    符合 API-IR 标准的单步测试模型
    """
    id: str
    name: str
    description: str = ""
    request: RefinedRequestSpec
    dependencies: List[str] = Field(default_factory=list)
    extraction: Dict[str, str] = Field(default_factory=dict)
    assertion: RefinedAssertionSpec = Field(default_factory=RefinedAssertionSpec)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RefinedTestCase(BaseModel):
    """
    Refined Test Case
    
    包含多个步骤的完整测试用例 (Chain)
    """
    id: str
    name: str
    description: str = ""
    steps: List[RefinedTestStep] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
