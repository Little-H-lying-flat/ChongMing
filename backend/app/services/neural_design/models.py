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

class DraftStep(BaseModel):
    """
    草稿步骤
    
    LLM 初步生成的测试步骤
    """
    step_id: str = Field(..., description="步骤 ID")
    intent: str = Field(..., description="测试意图")
    step_type: Literal["API", "UI"] = Field(..., description="步骤类型")
    method: str = Field(..., description="HTTP 方法 (API) 或 操作 (UI)")
    url_path: str = Field(..., description="URL 路径 (API) 或 元素定位 (UI)")
    description: str = Field(..., description="步骤描述")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据示例")
    expected_outcome: Optional[str] = Field(None, description="预期结果描述")
    expected_status_code: int = Field(..., description="[REQUIRED] Expected HTTP status code")
    json_assertions: Dict[str, Any] = Field(..., description="[REQUIRED] JSON assertions")

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

class RefinedTestStep(BaseModel):
    """
    Refined Test Step
    
    符合 API-IR 标准的单步测试模型
    """
    id: str = Field(..., description="步骤唯一标识")
    name: str = Field(..., description="步骤名称")
    step_type: Literal["API", "UI"] = Field("API", description="步骤类型")
    description: str = Field("", description="步骤详细描述")
    request: RefinedRequestSpec = Field(..., description="请求规范")
    dependencies: List[str] = Field(default_factory=list, description="依赖的前置步骤 ID")
    extract: Dict[str, str] = Field(default_factory=dict, description="Variables to extract from response. Key is variable name, Value is JSON path or field name (e.g., {'token': 'data.token'}).", example={"token": "$.data.token"})
    # Flattened Assertions (First Class Citizens)
    expected_status_code: int = Field(..., description="[REQUIRED] The explicit expected HTTP status code. If not specified in text, you MUST default to 200.")
    json_assertions: Dict[str, Any] = Field(..., description="[REQUIRED] Dictionary of expected JSON key-values. If none, output an empty dictionary {}.")
    # Deprecated: assertion field kept for backward compatibility but should be ignored in favor of above
    assertion: Optional[RefinedAssertionSpec] = Field(None, description="Legacy Assertion Spec (Deprecated)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

class RefinedTestCase(BaseModel):
    """
    Refined Test Case
    
    包含多个步骤的完整测试用例 (Chain)
    """
    id: str = Field(..., description="用例唯一标识")
    name: str = Field(..., description="用例名称")
    description: str = Field("", description="用例描述")
    steps: List[RefinedTestStep] = Field(default_factory=list, description="测试步骤序列")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="用例元数据")
