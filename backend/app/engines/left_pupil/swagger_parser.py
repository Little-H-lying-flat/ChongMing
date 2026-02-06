"""
Swagger/OpenAPI 解析器

解析 OpenAPI 3.0 / Swagger 2.0 文档，生成 API-IR
对应 Issue: #LP-001
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import yaml

from loguru import logger
import httpx


class OpenAPIVersion(str, Enum):
    """OpenAPI 版本"""
    SWAGGER_2 = "swagger_2"
    OPENAPI_3 = "openapi_3"


@dataclass
class ParameterInfo:
    """参数信息"""
    name: str
    location: str  # query, header, path, cookie
    required: bool = False
    schema_type: str = "string"
    description: str = ""
    example: Any = None
    enum: List[Any] = None


@dataclass
class RequestBodyInfo:
    """请求体信息"""
    content_type: str
    schema: Dict[str, Any]
    required: bool = False
    example: Any = None


@dataclass
class ResponseInfo:
    """响应信息"""
    status_code: str
    description: str
    schema: Optional[Dict[str, Any]] = None
    example: Any = None


@dataclass
class EndpointInfo:
    """端点信息"""
    path: str
    method: str
    operation_id: str
    summary: str
    description: str
    tags: List[str]
    parameters: List[ParameterInfo]
    request_body: Optional[RequestBodyInfo]
    responses: Dict[str, ResponseInfo]
    security: List[Dict[str, List[str]]]
    deprecated: bool = False


@dataclass
class APISpec:
    """API 规格"""
    title: str
    version: str
    description: str
    base_url: str
    openapi_version: OpenAPIVersion
    endpoints: List[EndpointInfo] = field(default_factory=list)
    security_schemes: Dict[str, Dict] = field(default_factory=dict)
    schemas: Dict[str, Dict] = field(default_factory=dict)


class SwaggerParser:
    """
    OpenAPI/Swagger 文档解析器
    
    支持:
    - OpenAPI 3.0.x
    - Swagger 2.0
    - JSON 和 YAML 格式
    - URL 和文件加载
    """
    
    def __init__(self):
        self._spec: Optional[Dict] = None
        self._version: Optional[OpenAPIVersion] = None
    
    async def load_from_url(self, url: str) -> APISpec:
        """从 URL 加载 OpenAPI 文档"""
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            if "yaml" in content_type or url.endswith((".yaml", ".yml")):
                self._spec = yaml.safe_load(response.text)
            else:
                self._spec = response.json()
        
        return self._parse()
    
    def load_from_file(self, file_path: str) -> APISpec:
        """从文件加载 OpenAPI 文档"""
        path = Path(file_path)
        
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                self._spec = yaml.safe_load(f)
            else:
                self._spec = json.load(f)
        
        return self._parse()
    
    def load_from_dict(self, spec: Dict) -> APISpec:
        """从字典加载 OpenAPI 文档"""
        self._spec = spec
        return self._parse()
    
    def _parse(self) -> APISpec:
        """解析 OpenAPI 文档"""
        if not self._spec:
            raise ValueError("未加载 OpenAPI 文档")
        
        # 检测版本
        if "openapi" in self._spec:
            self._version = OpenAPIVersion.OPENAPI_3
            return self._parse_openapi3()
        elif "swagger" in self._spec:
            self._version = OpenAPIVersion.SWAGGER_2
            return self._parse_swagger2()
        else:
            raise ValueError("无法识别的 OpenAPI 文档格式")
    
    def _parse_openapi3(self) -> APISpec:
        """解析 OpenAPI 3.0 文档"""
        info = self._spec.get("info", {})
        servers = self._spec.get("servers", [])
        
        # 基础 URL
        base_url = ""
        if servers:
            base_url = servers[0].get("url", "")
        
        api_spec = APISpec(
            title=info.get("title", "Unknown API"),
            version=info.get("version", "1.0.0"),
            description=info.get("description", ""),
            base_url=base_url,
            openapi_version=OpenAPIVersion.OPENAPI_3,
            security_schemes=self._spec.get("components", {}).get("securitySchemes", {}),
            schemas=self._spec.get("components", {}).get("schemas", {}),
        )
        
        # 解析端点
        paths = self._spec.get("paths", {})
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() in ("get", "post", "put", "delete", "patch", "head", "options"):
                    endpoint = self._parse_endpoint_v3(path, method.upper(), operation)
                    api_spec.endpoints.append(endpoint)
        
        logger.info(f"解析完成: {api_spec.title} v{api_spec.version}, {len(api_spec.endpoints)} 个端点")
        return api_spec
    
    def _parse_endpoint_v3(self, path: str, method: str, operation: Dict) -> EndpointInfo:
        """解析 OpenAPI 3.0 端点"""
        # 解析参数
        parameters = []
        for param in operation.get("parameters", []):
            parameters.append(ParameterInfo(
                name=param.get("name", ""),
                location=param.get("in", "query"),
                required=param.get("required", False),
                schema_type=param.get("schema", {}).get("type", "string"),
                description=param.get("description", ""),
                example=param.get("example"),
                enum=param.get("schema", {}).get("enum"),
            ))
        
        # 解析请求体
        request_body = None
        if "requestBody" in operation:
            rb = operation["requestBody"]
            content = rb.get("content", {})
            for content_type, content_schema in content.items():
                request_body = RequestBodyInfo(
                    content_type=content_type,
                    schema=content_schema.get("schema", {}),
                    required=rb.get("required", False),
                    example=content_schema.get("example"),
                )
                break  # 只取第一个
        
        # 解析响应
        responses = {}
        for status_code, response in operation.get("responses", {}).items():
            content = response.get("content", {})
            schema = None
            example = None
            for ct, cs in content.items():
                schema = cs.get("schema", {})
                example = cs.get("example")
                break
            
            responses[status_code] = ResponseInfo(
                status_code=status_code,
                description=response.get("description", ""),
                schema=schema,
                example=example,
            )
        
        return EndpointInfo(
            path=path,
            method=method,
            operation_id=operation.get("operationId", f"{method}_{path}"),
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            tags=operation.get("tags", []),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            security=operation.get("security", []),
            deprecated=operation.get("deprecated", False),
        )
    
    def _parse_swagger2(self) -> APISpec:
        """解析 Swagger 2.0 文档"""
        info = self._spec.get("info", {})
        
        # 基础 URL
        host = self._spec.get("host", "")
        base_path = self._spec.get("basePath", "")
        schemes = self._spec.get("schemes", ["https"])
        base_url = f"{schemes[0]}://{host}{base_path}" if host else ""
        
        api_spec = APISpec(
            title=info.get("title", "Unknown API"),
            version=info.get("version", "1.0.0"),
            description=info.get("description", ""),
            base_url=base_url,
            openapi_version=OpenAPIVersion.SWAGGER_2,
            security_schemes=self._spec.get("securityDefinitions", {}),
            schemas=self._spec.get("definitions", {}),
        )
        
        # 解析端点
        paths = self._spec.get("paths", {})
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() in ("get", "post", "put", "delete", "patch"):
                    endpoint = self._parse_endpoint_v2(path, method.upper(), operation)
                    api_spec.endpoints.append(endpoint)
        
        logger.info(f"解析完成 (Swagger 2.0): {api_spec.title}, {len(api_spec.endpoints)} 个端点")
        return api_spec
    
    def _parse_endpoint_v2(self, path: str, method: str, operation: Dict) -> EndpointInfo:
        """解析 Swagger 2.0 端点"""
        parameters = []
        request_body = None
        
        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                # Swagger 2.0 的 body 参数
                request_body = RequestBodyInfo(
                    content_type="application/json",
                    schema=param.get("schema", {}),
                    required=param.get("required", False),
                )
            else:
                parameters.append(ParameterInfo(
                    name=param.get("name", ""),
                    location=param.get("in", "query"),
                    required=param.get("required", False),
                    schema_type=param.get("type", "string"),
                    description=param.get("description", ""),
                    example=param.get("default"),
                    enum=param.get("enum"),
                ))
        
        responses = {}
        for status_code, response in operation.get("responses", {}).items():
            responses[status_code] = ResponseInfo(
                status_code=status_code,
                description=response.get("description", ""),
                schema=response.get("schema"),
            )
        
        return EndpointInfo(
            path=path,
            method=method,
            operation_id=operation.get("operationId", f"{method}_{path}"),
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            tags=operation.get("tags", []),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            security=operation.get("security", []),
            deprecated=operation.get("deprecated", False),
        )
    
    def generate_api_ir(self, endpoint: EndpointInfo, base_url: str = "") -> Dict:
        """
        将端点转换为 API-IR 格式
        
        Args:
            endpoint: 端点信息
            base_url: 基础 URL
            
        Returns:
            API-IR 字典
        """
        return {
            "method": endpoint.method,
            "url": f"{base_url}{endpoint.path}",
            "headers": {},
            "query_params": {
                p.name: p.example or f"${{{p.name}}}"
                for p in endpoint.parameters
                if p.location == "query"
            },
            "path_params": {
                p.name: p.example or f"${{{p.name}}}"
                for p in endpoint.parameters
                if p.location == "path"
            },
            "body": endpoint.request_body.example if endpoint.request_body else None,
            "assertions": [
                {"type": "status_code", "expected": 200},
            ],
            "extract": {},
            "metadata": {
                "operation_id": endpoint.operation_id,
                "summary": endpoint.summary,
                "tags": endpoint.tags,
            },
        }
