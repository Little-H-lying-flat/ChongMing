"""
API 执行器

执行 HTTP 请求并提取响应数据
"""

import time
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.services.left_pupil.context_memory import ContextMemory
from app.services.left_pupil.asserter import (
    Asserter, AssertionReport, AssertionRule, create_rules_from_dict
)


@dataclass
class RequestSpec:
    """请求规范"""
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[dict] = None
    query_params: dict[str, str] = field(default_factory=dict)
    timeout_ms: int = 30000


@dataclass
class ExtractionRule:
    """提取规则"""
    variable_name: str
    source: str  # "body", "header", "cookie"
    path: str    # JsonPath 或 Header 名


@dataclass
class ExecutionResult:
    """执行结果"""
    step_id: str
    status: str  # "passed", "failed", "error"
    status_code: int = 0
    response_body: Optional[dict] = None
    response_headers: dict[str, str] = field(default_factory=dict)
    request_method: str = ""
    request_url: str = ""
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: Optional[dict] = None
    duration_ms: float = 0.0
    extracted_values: dict[str, Any] = field(default_factory=dict)
    assertion_report: Optional[AssertionReport] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "extracted_values": self.extracted_values,
            "error": self.error,
            "assertions": {
                "passed": self.assertion_report.passed if self.assertion_report else True,
                "failed_count": self.assertion_report.failed_count if self.assertion_report else 0,
            } if self.assertion_report else None,
        }


@dataclass
class ApiIRStep:
    """API-IR 执行步骤"""
    id: str
    name: str = ""
    request: RequestSpec = field(default_factory=lambda: RequestSpec("GET", "/"))
    extraction: dict[str, str] = field(default_factory=dict)
    assertion: dict = field(default_factory=dict)
    retry_config: dict = field(default_factory=dict)


class ApiRunner:
    """
    API 执行器
    
    执行 HTTP 请求，提取响应数据，验证断言
    """
    
    def __init__(
        self,
        base_url: str,
        memory: Optional[ContextMemory] = None,
        default_headers: Optional[dict] = None,
    ):
        """
        初始化执行器
        
        Args:
            base_url: 基础 URL
            memory: 上下文内存
            default_headers: 默认请求头
        """
        self.base_url = base_url.rstrip("/")
        self.memory = memory or ContextMemory()
        self.default_headers = default_headers or {}
        self.asserter = Asserter()
        self._client: Optional[httpx.AsyncClient] = None
        self._results: list[ExecutionResult] = []
    
    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client
    
    async def execute(self, step: ApiIRStep) -> ExecutionResult:
        """
        执行单个步骤
        
        Args:
            step: API-IR 步骤
        
        Returns:
            执行结果
        """
        retry_config = step.retry_config or {}
        max_attempts = retry_config.get("max_attempts", 1)
        retry_on = retry_config.get("retry_on", [500, 502, 503])
        delay_ms = retry_config.get("delay_ms", 1000)
        
        last_result = None
        
        for attempt in range(max_attempts):
            result = await self._execute_once(step)
            last_result = result
            
            if result.status == "passed":
                return result
            
            # 检查是否需要重试
            if result.status_code not in retry_on:
                return result
            
            if attempt < max_attempts - 1:
                await self._sleep_ms(delay_ms * (2 ** attempt))
        
        return last_result or ExecutionResult(
            step_id=step.id,
            status="error",
            error="执行失败",
        )
    
    async def _execute_once(self, step: ApiIRStep) -> ExecutionResult:
        """执行一次请求"""
        request = step.request
        start_time = time.time()
        
        try:
            # 1. 注入变量
            url = self.memory.inject(request.url)
            
            # Automatically handle relative paths to prevent Protocol Errors 
            if url.startswith("/") and self.base_url:
                url = self.base_url + url
                
            headers = {**self.default_headers}
            for k, v in request.headers.items():
                headers[k] = self.memory.inject(v)
            
            body = None
            if request.body:
                body = self.memory.inject_dict(request.body)
            
            params = {}
            for k, v in request.query_params.items():
                params[k] = self.memory.inject(v)
            
            # 2. 发送请求
            response = await self.client.request(
                method=request.method,
                url=url,
                headers=headers,
                json=body,
                params=params,
                timeout=request.timeout_ms / 1000,
            )
            
            duration = (time.time() - start_time) * 1000
            
            # 3. 解析响应
            try:
                response_body = response.json()
            except Exception:
                response_body = {"_raw": response.text}
            
            response_headers = dict(response.headers)
            
            # 4. 提取变量
            extracted = {}
            for var_name, path in step.extraction.items():
                value = self._extract_value(response, response_body, path)
                if value is not None:
                    self.memory.set(var_name, value, source=step.id)
                    extracted[var_name] = value
            
            # 5. 执行断言
            assertion_report = None
            if step.assertion:
                rules = create_rules_from_dict(step.assertion)
                assertion_report = self.asserter.assert_all(
                    response_body, rules, response.status_code
                )
            
            # 6. 构建结果
            status = "passed"
            if assertion_report and not assertion_report.passed:
                status = "failed"
            
            result = ExecutionResult(
                step_id=step.id,
                status=status,
                status_code=response.status_code,
                response_body=response_body,
                response_headers=response_headers,
                request_method=request.method,
                request_url=url,
                request_headers=headers,
                request_body=body,
                duration_ms=duration,
                extracted_values=extracted,
                assertion_report=assertion_report,
            )
            
            self._results.append(result)
            return result
            
        except httpx.TimeoutException:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                step_id=step.id,
                status="error",
                duration_ms=duration,
                error="请求超时",
            )
        except httpx.ConnectError as e:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                step_id=step.id,
                status="error",
                duration_ms=duration,
                error=f"连接失败: {str(e)}",
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                step_id=step.id,
                status="error",
                duration_ms=duration,
                error=f"执行错误: {str(e)}",
            )
    
    def _extract_value(
        self,
        response: httpx.Response,
        body: dict,
        path: str,
    ) -> Any:
        """从响应中提取值"""
        if path.startswith("header:"):
            header_name = path[7:]
            return response.headers.get(header_name)
        
        if path.startswith("cookie:"):
            cookie_name = path[7:]
            return response.cookies.get(cookie_name)
        
        if path.startswith("regex:"):
            import re
            pattern = path[6:]
            match = re.search(pattern, str(body))
            return match.group(1) if match else None
        
        # JsonPath
        return self._extract_json_path(body, path)
    
    def _extract_json_path(self, data: dict, path: str) -> Any:
        """提取 JsonPath 值"""
        # 优先使用 jsonpath-ng
        try:
            jsonpath_expr = parse(path)
            matches = jsonpath_expr.find(data)
            if matches:
                return matches[0].value
            # If no matches found by jsonpath-ng, fall through to simple implementation
            # This allows supporting ad-hoc syntax like $.0.id which jsonpath-ng rejects/ignores
        except ImportError:
            pass
        except Exception:
            pass
        except Exception:
            pass

        # 简单实现回退
        if path.startswith("$."):
            path = path[2:]
        
        current = data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None
        
        return current
    
    async def _sleep_ms(self, ms: float):
        """异步睡眠"""
        import asyncio
        await asyncio.sleep(ms / 1000)
    
    def get_results(self) -> list[ExecutionResult]:
        """获取所有执行结果"""
        return list(self._results)
    
    def clear_results(self):
        """清空执行结果"""
        self._results.clear()
    
    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
