from typing import List, Optional, Dict, Any, Union, Literal
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
    target_type: Literal["API", "UI", "MIXED"] = Field("MIXED", description="生成目标类型")

class DraftApiStep(BaseModel):
    step_id: str = Field(..., description="步骤 ID")
    intent: str = Field(..., description="测试意图")
    step_type: Literal["API"] = "API"
    method: str = Field(..., description="HTTP Method")
    url_path: str = Field(..., description="URL Path")
    description: str = Field(..., description="步骤描述")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Request Body")
    expected_status_code: int = Field(..., description="Expected HTTP Status")
    json_assertions: Dict[str, Any] = Field(default_factory=dict, description="JSON Assertions")
    extract: Dict[str, str] = Field(default_factory=dict, description="Variable Extraction")

class DraftUiStep(BaseModel):
    step_id: str = Field(..., description="步骤 ID")
    intent: str = Field(..., description="测试意图")
    step_type: Literal["UI"] = "UI"
    action: Literal["goto", "click", "type", "assert", "screenshot", "wait", "scroll", "hover"] = Field(..., description="UI Action")
    target: str = Field(..., description="Element selector or description")
    value: Optional[str] = Field(None, description="Input value")
    description: str = Field(..., description="步骤描述")
    expected_visual_change: Optional[str] = Field(None, description="Expected visual change")

DraftStep = Union[DraftApiStep, DraftUiStep]

class DraftTestCase(BaseModel):
    """
    草稿测试用例
    """
    case_name: str = Field(..., description="用例名称")
    description: str = Field(..., description="用例描述")
    steps: List[DraftStep] = Field(..., description="测试步骤列表")
    tags: List[str] = Field(default_factory=list, description="标签")

class RefinedRequestSpec(BaseModel):
    """请求规范 (Pydantic版)"""
    method: str = Field(..., description="HTTP 请求方法 (GET, POST, PUT, DELETE 等)", example="POST")
    url: str = Field(..., description="请求目标 URL", example="https://api.example.com/v1/login")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP 请求头", example={"Content-Type": "application/json"})
    body: Optional[Dict[str, Any]] = Field(None, description="请求体 (JSON)", example={"username": "admin", "password": "***"})
    query_params: Dict[str, str] = Field(default_factory=dict, description="URL 查询参数", example={"page": "1", "size": "10"})
    timeout_ms: int = Field(30000, description="请求超时时间 (毫秒)")

class RefinedAssertionSpec(BaseModel):
    """断言规范 (Pydantic版)"""
    status_code: int = Field(200, description="MUST extract the explicit expected HTTP status code (e.g., 200, 403, 500).", example=200)
    schema_validate: bool = Field(False, description="是否进行 Schema 校验")
    json_assertions: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of JSON path/keys and expected values to assert in the response body. e.g. {'data.first_name': '孙悟空'}", example={"$.data.id": 123})
    contains: Optional[str] = Field(None, description="响应体包含的字符串")
    expression: Optional[str] = Field(None, description="自定义 Python 表达式断言")

class RefinedApiStep(BaseModel):
    id: str = Field(..., description="步骤唯一标识")
    name: str = Field(..., description="步骤名称")
    step_type: Literal["API"] = "API"
    description: str = Field("", description="步骤详细描述")
    request: RefinedRequestSpec = Field(..., description="请求规范")
    dependencies: List[str] = Field(default_factory=list, description="依赖的前置步骤 ID")
    extract: Dict[str, str] = Field(default_factory=dict, description="Variables to extract")
    expected_status_code: int = Field(..., description="Expected Status Code")
    json_assertions: Dict[str, Any] = Field(default_factory=dict, description="JSON Assertions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

class RefinedUiStep(BaseModel):
    id: str = Field(..., description="步骤唯一标识")
    name: str = Field(..., description="步骤名称")
    step_type: Literal["UI"] = "UI"
    description: str = Field("", description="步骤详细描述")
    action: Literal["goto", "click", "type", "assert", "screenshot", "wait", "scroll", "hover"] = Field(..., description="UI Action")
    target: str = Field(..., description="Target Element")
    value: Optional[str] = Field(None, description="Input Value")
    dependencies: List[str] = Field(default_factory=list, description="依赖的前置步骤 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

RefinedTestStep = Union[RefinedApiStep, RefinedUiStep]

class RefinedTestCase(BaseModel):
    """
    Refined Test Case
    """
    id: str = Field(..., description="用例唯一标识")
    name: str = Field(..., description="用例名称")
    description: str = Field("", description="用例描述")
    steps: List[RefinedTestStep] = Field(default_factory=list, description="测试步骤序列")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="用例元数据")
