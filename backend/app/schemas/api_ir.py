from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field

class AuthType(str, Enum):
    """认证类型"""
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"


@dataclass
class AuthConfig:
    """认证配置"""
    auth_type: AuthType = Field(AuthType.NONE, description="认证类型 (none, bearer, basic, api_key)")
    token: Optional[str] = Field(None, description="Bearer Token 值")
    username: Optional[str] = Field(None, description="Basic Auth 用户名")
    password: Optional[str] = Field(None, description="Basic Auth 密码")
    api_key_name: Optional[str] = Field(None, description="API Key 名称 (如 X-API-Key)")
    api_key_value: Optional[str] = Field(None, description="API Key 值")
    api_key_location: str = Field("header", description="API Key 位置 (header, query)")


@dataclass
class APIIR:
    """API 中间表示 (Intermediate Representation)"""
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, Any] = field(default_factory=dict)
    path_params: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Any] = None
    content_type: str = "application/json"
    timeout: float = 30.0
    expected_status_code: Optional[int] = None
    json_assertions: Dict[str, Any] = field(default_factory=dict)
    assertions: List[Dict] = field(default_factory=list)
    extract: Dict[str, str] = field(default_factory=dict)
    # Turbo Engine extensions (Optional)
    weight: int = 1  # 压测权重


@dataclass
class APIResponse:
    """API 响应"""
    status_code: int
    headers: Dict[str, str]
    body: Any
    raw_body: bytes
    duration_ms: float
    request_url: str
    request_method: str


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    response: Optional[APIResponse]
    assertions_passed: List[str]
    assertions_failed: List[str]
    extracted_values: Dict[str, Any]
    error: Optional[str] = None
