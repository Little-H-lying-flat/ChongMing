"""
API-IR 执行器

执行 API 中间表示，发送 HTTP 请求
对应 Issue: #LP-002
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import re
import time

import httpx
from loguru import logger


class AuthType(str, Enum):
    """认证类型"""
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"


@dataclass
class AuthConfig:
    """认证配置"""
    auth_type: AuthType = AuthType.NONE
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key_name: Optional[str] = None
    api_key_value: Optional[str] = None
    api_key_location: str = "header"  # header, query


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
    assertions: List[Dict] = field(default_factory=list)
    extract: Dict[str, str] = field(default_factory=dict)


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


class APIExecutor:
    """
    API-IR 执行器
    
    功能:
    - HTTP 请求发送
    - 认证处理
    - 变量替换
    - 响应解析
    """
    
    def __init__(
        self,
        auth_config: Optional[AuthConfig] = None,
        default_headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        self.auth_config = auth_config or AuthConfig()
        self.default_headers = default_headers or {}
        self.timeout = timeout
        self._context: Dict[str, Any] = {}
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._client:
            await self._client.aclose()
    
    def set_context(self, key: str, value: Any):
        """设置上下文变量"""
        self._context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文变量"""
        return self._context.get(key, default)
    
    def update_context(self, values: Dict[str, Any]):
        """批量更新上下文"""
        self._context.update(values)
    
    async def execute(self, api_ir: APIIR) -> ExecutionResult:
        """
        执行 API-IR
        
        Args:
            api_ir: API 中间表示
            
        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        
        try:
            # 1. 变量替换
            url = self._replace_variables(api_ir.url)
            url = self._replace_path_params(url, api_ir.path_params)
            headers = self._build_headers(api_ir)
            body = self._replace_variables_in_obj(api_ir.body) if api_ir.body else None
            params = {k: self._replace_variables(str(v)) for k, v in api_ir.query_params.items()}
            
            logger.info(f"执行 API: {api_ir.method} {url}")
            
            # 2. 发送请求
            if not self._client:
                self._client = httpx.AsyncClient(timeout=self.timeout)
            
            response = await self._client.request(
                method=api_ir.method,
                url=url,
                headers=headers,
                params=params,
                json=body if api_ir.content_type == "application/json" else None,
                content=body if api_ir.content_type != "application/json" else None,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # 3. 解析响应
            try:
                response_body = response.json()
            except:
                response_body = response.text
            
            api_response = APIResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                raw_body=response.content,
                duration_ms=duration_ms,
                request_url=url,
                request_method=api_ir.method,
            )
            
            # 4. 变量提取
            extracted = self._extract_values(response_body, api_ir.extract)
            self._context.update(extracted)
            
            # 5. 断言验证
            from app.engines.left_pupil.assertion_engine import AssertionEngine
            assertion_engine = AssertionEngine()
            assertion_result = assertion_engine.run_assertions(
                api_ir.assertions,
                api_response,
            )
            
            success = len(assertion_result["failed"]) == 0
            
            return ExecutionResult(
                success=success,
                response=api_response,
                assertions_passed=assertion_result["passed"],
                assertions_failed=assertion_result["failed"],
                extracted_values=extracted,
            )
            
        except Exception as e:
            logger.error(f"API 执行失败: {e}")
            return ExecutionResult(
                success=False,
                response=None,
                assertions_passed=[],
                assertions_failed=[],
                extracted_values={},
                error=str(e),
            )
    
    def _build_headers(self, api_ir: APIIR) -> Dict[str, str]:
        """构建请求头"""
        headers = {**self.default_headers, **api_ir.headers}
        
        # Content-Type
        if api_ir.body and "Content-Type" not in headers:
            headers["Content-Type"] = api_ir.content_type
        
        # 认证
        if self.auth_config.auth_type == AuthType.BEARER:
            headers["Authorization"] = f"Bearer {self.auth_config.token}"
        
        elif self.auth_config.auth_type == AuthType.BASIC:
            import base64
            credentials = f"{self.auth_config.username}:{self.auth_config.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        
        elif self.auth_config.auth_type == AuthType.API_KEY:
            if self.auth_config.api_key_location == "header":
                headers[self.auth_config.api_key_name] = self.auth_config.api_key_value
        
        # 变量替换
        return {k: self._replace_variables(v) for k, v in headers.items()}
    
    def _replace_variables(self, text: str) -> str:
        """替换变量占位符 ${variable}"""
        if not isinstance(text, str):
            return text
        
        pattern = r'\$\{(\w+)\}'
        
        def replacer(match):
            var_name = match.group(1)
            return str(self._context.get(var_name, match.group(0)))
        
        return re.sub(pattern, replacer, text)
    
    def _replace_path_params(self, url: str, path_params: Dict[str, Any]) -> str:
        """替换路径参数 {param}"""
        for name, value in path_params.items():
            url = url.replace(f"{{{name}}}", str(self._replace_variables(str(value))))
        return url
    
    def _replace_variables_in_obj(self, obj: Any) -> Any:
        """递归替换对象中的变量"""
        if isinstance(obj, str):
            return self._replace_variables(obj)
        elif isinstance(obj, dict):
            return {k: self._replace_variables_in_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_variables_in_obj(item) for item in obj]
        return obj
    
    def _extract_values(self, body: Any, extract_rules: Dict[str, str]) -> Dict[str, Any]:
        """提取响应值"""
        from app.engines.left_pupil.variable_extractor import VariableExtractor
        extractor = VariableExtractor()
        
        extracted = {}
        for var_name, rule in extract_rules.items():
            try:
                value = extractor.extract(body, rule)
                extracted[var_name] = value
                logger.debug(f"提取变量: {var_name} = {value}")
            except Exception as e:
                logger.warning(f"提取变量失败: {var_name} - {e}")
        
        return extracted
