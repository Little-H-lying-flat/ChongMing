from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

# Re-export AUIIR from existing schema for compatibility
from app.schemas.aui_ir import VisualActionIR as AUIIR

class ExecutionMode(Enum):
    """执行模式"""
    UI = "UI"          # UI 自动化
    API = "API"        # API 自动化
    HYBRID = "HYBRID"  # 混合模式

@dataclass
class TCIR:
    """TC-IR 协议 (Test Case Intermediate Representation)"""
    id: str
    name: str
    mode: ExecutionMode
    steps: List[dict]
    priority: str = "P1"
    tags: List[str] = None

@dataclass
class StepResult:
    """步骤执行结果"""
    step_index: int
    success: bool
    duration_ms: float
    screenshot: Optional[str] = None
    error: Optional[str] = None
    error: Optional[str] = None
    details: Optional[dict] = None
    description: Optional[str] = None

@dataclass
class ExecutionResult:
    """用例执行结果"""
    tc_id: str
    success: bool
    status: str  # passed, failed, skipped, error
    step_results: List[StepResult]
    total_duration_ms: float
    step_results: List[StepResult]
    total_duration_ms: float
    trace_id: str
    error: Optional[str] = None
    variable_trace: List[dict] = None  # New: Variable Extraction Audit Log

# API Related Schemas (Moved from left_pupil.py)

class HTTPMethod(Enum):
    """HTTP 方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

@dataclass
class APISpec:
    """API 规格定义"""
    path: str
    method: HTTPMethod
    summary: str
    parameters: List[dict]
    request_body: Optional[dict]
    responses: Dict[str, dict]

@dataclass
class APIIR:
    """API-IR 协议 (API Intermediate Representation)"""
    method: str
    url: str
    headers: Dict[str, str]
    query_params: Dict[str, Any]
    body: Optional[Any]
    assertions: List[dict]
    extract: Dict[str, str]  # JSONPath 提取

@dataclass
class APIResult:
    """API 执行结果"""
    success: bool
    status_code: int
    headers: Dict[str, str]
    body: Any
    duration_ms: float
    assertions_passed: List[str]
    assertions_failed: List[str]
    extracted_values: Dict[str, Any]
    error: Optional[str] = None
