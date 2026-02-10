"""
Swagger/OpenAPI 文档解析器

支持 OpenAPI 3.0/3.1, Swagger 2.0 格式
"""

import json
import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class SpecFormat(Enum):
    """文档格式"""
    OPENAPI_3 = "openapi3"
    SWAGGER_2 = "swagger2"
    UNKNOWN = "unknown"


@dataclass
class Parameter:
    """API 参数"""
    name: str
    location: str  # path, query, header, cookie
    required: bool = False
    description: str = ""
    schema_type: str = "string"
    default: Any = None
    enum: list[str] = field(default_factory=list)


@dataclass
class RequestBody:
    """请求体"""
    content_type: str = "application/json"
    required: bool = True
    schema: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class Response:
    """响应定义"""
    status_code: str
    description: str = ""
    schema: dict = field(default_factory=dict)


@dataclass
class ApiEndpoint:
    """API 端点"""
    id: str                              # "POST /api/v1/orders"
    path: str                            # "/api/v1/orders"
    method: str                          # "POST"
    summary: str = ""
    description: str = ""
    operation_id: Optional[str] = None
    parameters: list[Parameter] = field(default_factory=list)
    request_body: Optional[RequestBody] = None
    responses: dict[str, Response] = field(default_factory=dict)
    security: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "path": self.path,
            "method": self.method,
            "summary": self.summary,
            "description": self.description,
            "operation_id": self.operation_id,
            "parameters": [
                {
                    "name": p.name,
                    "location": p.location,
                    "required": p.required,
                    "schema_type": p.schema_type,
                }
                for p in self.parameters
            ],
            "has_request_body": self.request_body is not None,
            "security": self.security,
            "tags": self.tags,
        }
    
    def to_searchable_text(self) -> str:
        """生成可搜索文本"""
        parts = [
            f"接口: {self.method} {self.path}",
            f"摘要: {self.summary}" if self.summary else "",
            f"描述: {self.description}" if self.description else "",
            f"标签: {', '.join(self.tags)}" if self.tags else "",
        ]
        
        if self.parameters:
            param_texts = []
            for p in self.parameters:
                req = "必填" if p.required else "可选"
                param_texts.append(f"{p.name}({p.location}, {req})")
            parts.append(f"参数: {', '.join(param_texts)}")
        
        if self.request_body:
            parts.append(f"请求体: {self.request_body.content_type}")
        
        if self.security:
            parts.append("认证: 需要")
        
        return "\n".join(p for p in parts if p)


class SwaggerParser:
    """
    Swagger/OpenAPI 解析器
    
    支持:
    - OpenAPI 3.0/3.1
    - Swagger 2.0
    """
    
    def __init__(self):
        self._spec: dict = {}
        self._format: SpecFormat = SpecFormat.UNKNOWN
        self._base_path: str = ""
    
    def parse_file(self, file_path: str) -> list[ApiEndpoint]:
        """
        解析文件
        
        Args:
            file_path: 文件路径 (JSON 或 YAML)
        
        Returns:
            API 端点列表
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        
        if path.suffix.lower() in [".yaml", ".yml"]:
            spec = yaml.safe_load(content)
        else:
            spec = json.loads(content)
        
        return self.parse(spec)
    
    def parse_url(self, url: str) -> list[ApiEndpoint]:
        """
        从 URL 解析
        
        Args:
            url: Swagger 文档 URL
        
        Returns:
            API 端点列表
        """
        import httpx
        
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "")
        if "yaml" in content_type or url.endswith((".yaml", ".yml")):
            spec = yaml.safe_load(response.text)
        else:
            spec = response.json()
        
        return self.parse(spec)
    
    def parse(self, spec: dict) -> list[ApiEndpoint]:
        """
        解析规范字典
        
        Args:
            spec: OpenAPI/Swagger 规范字典
        
        Returns:
            API 端点列表
        """
        self._spec = spec
        self._format = self._detect_format()
        self._base_path = self._get_base_path()
        
        endpoints = []
        paths = spec.get("paths", {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() in ["get", "post", "put", "patch", "delete", "head", "options"]:
                    endpoint = self._parse_endpoint(path, method, details)
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _detect_format(self) -> SpecFormat:
        """检测规范格式"""
        if "openapi" in self._spec:
            return SpecFormat.OPENAPI_3
        elif "swagger" in self._spec:
            return SpecFormat.SWAGGER_2
        return SpecFormat.UNKNOWN
    
    def _get_base_path(self) -> str:
        """获取基础路径"""
        if self._format == SpecFormat.SWAGGER_2:
            return self._spec.get("basePath", "")
        elif self._format == SpecFormat.OPENAPI_3:
            servers = self._spec.get("servers", [])
            if servers:
                return servers[0].get("url", "")
        return ""
    
    def _parse_endpoint(self, path: str, method: str, details: dict) -> ApiEndpoint:
        """解析单个端点"""
        method_upper = method.upper()
        endpoint_id = f"{method_upper} {path}"
        
        parameters = self._parse_parameters(details.get("parameters", []))
        request_body = self._parse_request_body(details)
        responses = self._parse_responses(details.get("responses", {}))
        
        return ApiEndpoint(
            id=endpoint_id,
            path=path,
            method=method_upper,
            summary=details.get("summary", ""),
            description=details.get("description", ""),
            operation_id=details.get("operationId"),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            security=details.get("security", []),
            tags=details.get("tags", []),
            deprecated=details.get("deprecated", False),
        )
    
    def _parse_parameters(self, params: list) -> list[Parameter]:
        """解析参数列表"""
        result = []
        for p in params:
            # 解析 $ref
            if "$ref" in p:
                p = self._resolve_ref(p["$ref"])
            
            schema = p.get("schema", {})
            result.append(Parameter(
                name=p.get("name", ""),
                location=p.get("in", "query"),
                required=p.get("required", False),
                description=p.get("description", ""),
                schema_type=schema.get("type", p.get("type", "string")),
                default=schema.get("default", p.get("default")),
                enum=schema.get("enum", p.get("enum", [])),
            ))
        return result
    
    def _parse_request_body(self, details: dict) -> Optional[RequestBody]:
        """解析请求体"""
        # OpenAPI 3.x
        if "requestBody" in details:
            rb = details["requestBody"]
            content = rb.get("content", {})
            
            # 优先 JSON
            if "application/json" in content:
                return RequestBody(
                    content_type="application/json",
                    required=rb.get("required", True),
                    schema=content["application/json"].get("schema", {}),
                    description=rb.get("description", ""),
                )
            
            # 其他类型
            for ct, spec in content.items():
                return RequestBody(
                    content_type=ct,
                    required=rb.get("required", True),
                    schema=spec.get("schema", {}),
                    description=rb.get("description", ""),
                )
        
        # Swagger 2.x - body 参数
        for p in details.get("parameters", []):
            if p.get("in") == "body":
                return RequestBody(
                    content_type="application/json",
                    required=p.get("required", True),
                    schema=p.get("schema", {}),
                    description=p.get("description", ""),
                )
        
        return None
    
    def _parse_responses(self, responses: dict) -> dict[str, Response]:
        """解析响应定义"""
        result = {}
        for status_code, details in responses.items():
            schema = {}
            
            # OpenAPI 3.x
            content = details.get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
            
            # Swagger 2.x
            if "schema" in details:
                schema = details["schema"]
            
            result[status_code] = Response(
                status_code=status_code,
                description=details.get("description", ""),
                schema=schema,
            )
        return result
    
    def _resolve_ref(self, ref: str) -> dict:
        """解析 $ref 引用"""
        if not ref.startswith("#/"):
            return {}
        
        parts = ref[2:].split("/")
        current = self._spec
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {}
        
        return current if isinstance(current, dict) else {}
    
    def get_info(self) -> dict:
        """获取 API 基本信息"""
        info = self._spec.get("info", {})
        return {
            "title": info.get("title", ""),
            "version": info.get("version", ""),
            "description": info.get("description", ""),
            "format": self._format.value,
            "base_path": self._base_path,
        }
    
    def get_tags(self) -> list[dict]:
        """获取标签列表"""
        return self._spec.get("tags", [])
    
    def get_security_schemes(self) -> dict:
        """获取认证方案"""
        if self._format == SpecFormat.OPENAPI_3:
            components = self._spec.get("components", {})
            return components.get("securitySchemes", {})
        elif self._format == SpecFormat.SWAGGER_2:
            return self._spec.get("securityDefinitions", {})
        return {}
