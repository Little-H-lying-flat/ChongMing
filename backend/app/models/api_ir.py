"""
API-IR 协议模型

定义 API 测试的中间表示格式
"""

from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import uuid


class ApiIRVersion(Enum):
    """协议版本"""
    V1 = "1.0"
    V2 = "2.0"


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    delay_ms: int = 1000
    retry_on: list[int] = field(default_factory=lambda: [500, 502, 503])
    
    def to_dict(self) -> dict:
        return {
            "max_attempts": self.max_attempts,
            "delay_ms": self.delay_ms,
            "retry_on": self.retry_on,
        }


@dataclass
class RequestSpec:
    """请求规范"""
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[dict] = None
    query_params: dict[str, str] = field(default_factory=dict)
    timeout_ms: int = 30000
    
    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "body": self.body,
            "query_params": self.query_params,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class AssertionSpec:
    """断言规范"""
    status_code: Optional[int] = None
    schema_validate: bool = False
    json_assertions: dict[str, Any] = field(default_factory=dict)
    contains: Optional[str] = None
    expression: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {}
        if self.status_code is not None:
            result["status_code"] = self.status_code
        if self.schema_validate:
            result["schema_validate"] = True
        if self.json_assertions:
            result["json_assertions"] = self.json_assertions
        if self.contains:
            result["contains"] = self.contains
        if self.expression:
            result["expression"] = self.expression
        return result


@dataclass
class ApiIR:
    """
    API 中间表示
    
    表示一个完整的 API 调用步骤
    """
    id: str
    name: str
    request: RequestSpec
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    extraction: dict[str, str] = field(default_factory=dict)
    assertion: AssertionSpec = field(default_factory=AssertionSpec)
    retry: RetryConfig = field(default_factory=RetryConfig)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "protocol": "API-IR",
            "version": ApiIRVersion.V2.value,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "request": self.request.to_dict(),
            "dependencies": self.dependencies,
            "extraction": self.extraction,
            "assertion": self.assertion.to_dict(),
            "retry": self.retry.to_dict(),
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ApiIR":
        """从字典创建"""
        request_data = data.get("request", {})
        request = RequestSpec(
            method=request_data.get("method", "GET"),
            url=request_data.get("url", "/"),
            headers=request_data.get("headers", {}),
            body=request_data.get("body"),
            query_params=request_data.get("query_params", {}),
            timeout_ms=request_data.get("timeout_ms", 30000),
        )
        
        assertion_data = data.get("assertion", {})
        assertion = AssertionSpec(
            status_code=assertion_data.get("status_code"),
            schema_validate=assertion_data.get("schema_validate", False),
            json_assertions=assertion_data.get("json_assertions", {}),
            contains=assertion_data.get("contains"),
            expression=assertion_data.get("expression"),
        )
        
        retry_data = data.get("retry", {})
        retry = RetryConfig(
            max_attempts=retry_data.get("max_attempts", 3),
            delay_ms=retry_data.get("delay_ms", 1000),
            retry_on=retry_data.get("retry_on", [500, 502, 503]),
        )
        
        return cls(
            id=data.get("id", f"STEP_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            request=request,
            dependencies=data.get("dependencies", []),
            extraction=data.get("extraction", {}),
            assertion=assertion,
            retry=retry,
            metadata=data.get("metadata", {}),
        )


@dataclass
class ApiIRChain:
    """
    API-IR 执行链
    
    表示一组有序的 API 调用
    """
    id: str
    name: str
    steps: list[ApiIR] = field(default_factory=list)
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": len(self.steps),
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ApiIRChain":
        """从字典创建"""
        steps = [ApiIR.from_dict(s) for s in data.get("steps", [])]
        
        return cls(
            id=data.get("id", f"CHAIN_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=steps,
            metadata=data.get("metadata", {}),
        )
    
    def add_step(self, step: ApiIR) -> None:
        """添加步骤"""
        self.steps.append(step)
    
    def get_step(self, step_id: str) -> Optional[ApiIR]:
        """获取步骤"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None


def create_api_ir(
    method: str,
    url: str,
    name: str = "",
    step_id: Optional[str] = None,
    headers: Optional[dict] = None,
    body: Optional[dict] = None,
    extraction: Optional[dict] = None,
    assertion: Optional[dict] = None,
) -> ApiIR:
    """
    快速创建 API-IR
    
    Args:
        method: HTTP 方法
        url: 请求 URL
        name: 步骤名称
        step_id: 步骤 ID
        headers: 请求头
        body: 请求体
        extraction: 提取规则
        assertion: 断言规则
    
    Returns:
        ApiIR 实例
    """
    request = RequestSpec(
        method=method.upper(),
        url=url,
        headers=headers or {},
        body=body,
    )
    
    assertion_spec = AssertionSpec()
    if assertion:
        assertion_spec = AssertionSpec(
            status_code=assertion.get("status_code"),
            json_assertions=assertion.get("json_assertions", {}),
            contains=assertion.get("contains"),
            expression=assertion.get("expression"),
        )
    
    return ApiIR(
        id=step_id or f"STEP_{uuid.uuid4().hex[:8]}",
        name=name or f"{method.upper()} {url}",
        request=request,
        extraction=extraction or {},
        assertion=assertion_spec,
    )
