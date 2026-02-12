"""
左瞳引擎 (Left Pupil Engine)

所属层级：执行层 (Execution Layer) - API 侧
设计哲学：Spec-Driven, Chain-Aware (规格驱动，链路感知)

核心职责:
- API 规格解析 (Spec Parsing)：解析 Swagger/OpenAPI 文档
- 调用链推理 (Chain Inference)：理解 API 依赖关系
- 智能请求构造 (Smart Request)：LLM 生成请求参数
- 断言验证 (Assertion)：响应校验和断言
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import httpx
from loguru import logger

from app.core.config import settings
from app.schemas.execution import (
    HTTPMethod,
    APISpec,
    APIIR,
    APIResult
)


class LeftPupilEngine:
    """
    左瞳引擎 - API 自动化执行核心
    
    工作流程:
    1. 解析 API-IR 指令
    2. 变量替换 (来自上下文)
    3. 发送 HTTP 请求
    4. 执行断言验证
    5. 提取响应数据 (供后续步骤使用)
    """
    
    def __init__(self, base_url: str = None, timeout: float = 30.0):
        self.base_url = base_url or ""
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
    
    async def execute(self, api_ir: APIIR) -> APIResult:
        """
        执行 API-IR 指令
        
        Args:
            api_ir: API 中间表示
            
        Returns:
            APIResult: 执行结果
        """
        import time
        start_time = time.time()
        
        try:
            # 1. 变量替换
            url = self._replace_variables(api_ir.url)
            headers = {k: self._replace_variables(v) for k, v in api_ir.headers.items()}
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
                json=body,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # 3. 解析响应
            try:
                response_body = response.json()
            except:
                response_body = response.text
            
            # 4. 断言验证
            assertions_passed = []
            assertions_failed = []
            
            for assertion in api_ir.assertions:
                passed = self._check_assertion(assertion, response, response_body)
                if passed:
                    assertions_passed.append(assertion.get("description", str(assertion)))
                else:
                    assertions_failed.append(assertion.get("description", str(assertion)))
            
            # 5. 数据提取
            extracted = {}
            for key, jsonpath in api_ir.extract.items():
                try:
                    value = self._extract_jsonpath(response_body, jsonpath)
                    extracted[key] = value
                    self._context[key] = value  # 存入上下文
                except Exception as e:
                    logger.warning(f"提取 {key} 失败: {e}")
            
            success = len(assertions_failed) == 0
            
            return APIResult(
                success=success,
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                duration_ms=duration_ms,
                assertions_passed=assertions_passed,
                assertions_failed=assertions_failed,
                extracted_values=extracted,
            )
            
        except Exception as e:
            logger.error(f"API 执行失败: {e}")
            return APIResult(
                success=False,
                status_code=0,
                headers={},
                body=None,
                duration_ms=(time.time() - start_time) * 1000,
                assertions_passed=[],
                assertions_failed=[],
                extracted_values={},
                error=str(e),
            )
    
    def _replace_variables(self, text: str) -> str:
        """替换变量占位符 ${variable}"""
        import re
        pattern = r'\$\{(\w+)\}'
        
        def replacer(match):
            var_name = match.group(1)
            return str(self._context.get(var_name, match.group(0)))
        
        return re.sub(pattern, replacer, text)
    
    def _replace_variables_in_obj(self, obj: Any) -> Any:
        """递归替换对象中的变量"""
        if isinstance(obj, str):
            return self._replace_variables(obj)
        elif isinstance(obj, dict):
            return {k: self._replace_variables_in_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_variables_in_obj(item) for item in obj]
        return obj
    
    def _check_assertion(
        self, 
        assertion: dict, 
        response: httpx.Response, 
        body: Any
    ) -> bool:
        """检查断言"""
        assertion_type = assertion.get("type")
        
        if assertion_type == "status_code":
            return response.status_code == assertion.get("expected")
        
        elif assertion_type == "json_path":
            try:
                actual = self._extract_jsonpath(body, assertion.get("path"))
                expected = assertion.get("expected")
                return actual == expected
            except:
                return False
        
        elif assertion_type == "contains":
            text = str(body)
            return assertion.get("expected") in text
        
        return False
    
    def _extract_jsonpath(self, obj: Any, path: str) -> Any:
        """简单的 JSONPath 提取 (支持 $.key.subkey 格式)"""
        if not path.startswith("$."):
            return obj
        
        keys = path[2:].split(".")
        current = obj
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                current = current[int(key)]
            else:
                raise KeyError(f"无法访问 {key}")
        
        return current
