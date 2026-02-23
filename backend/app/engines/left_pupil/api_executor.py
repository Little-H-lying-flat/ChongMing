"""
API-IR 执行器

执行 API 中间表示，发送 HTTP 请求
对应 Issue: #LP-002
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import re
import time

import httpx
from loguru import logger

from app.schemas.api_ir import APIIR, APIResponse, AuthConfig, AuthType, ExecutionResult


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
        self._client = httpx.AsyncClient(timeout=self.timeout, trust_env=False)
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
    
    async def execute(self, api_ir: APIIR, context: Dict[str, Any] = None) -> ExecutionResult:
        """
        执行 API-IR
        
        Args:
            api_ir: API 中间表示
            context: 执行上下文 (用于变量替换和提取)
            
        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        
        # Merge context: passed context takes precedence, fallback to self._context
        # We work with the passed mutable context dict to ensure updates flow back to Dispatcher
        active_context = context if context is not None else self._context
        
        try:
            # 1. 变量替换
            url = self._replace_variables(api_ir.url, active_context)
            url = self._replace_path_params(url, api_ir.path_params, active_context)
            headers = self._build_headers(api_ir, active_context)
            body = self._replace_variables_in_obj(api_ir.body, active_context) if api_ir.body else None
            params = {k: self._replace_variables(str(v), active_context) for k, v in api_ir.query_params.items()}
            
            # 1.5. URL 强制清洗与校验
            if not url:
                # 打印“尸体” (原始数据) 以便调试
                logger.error(f"提取 URL 失败！当前 step 数据: {api_ir}")
                raise ValueError("解析到的 URL 为空！请检查大模型生成的用例结构。")

            # 自动补全协议头
            if not url.startswith(("http://", "https://")):
                protocol = "http://" if "localhost" in url or "127.0.0.1" in url else "https://"
                url = f"{protocol}{url}"
                logger.warning(f"URL 缺少协议头，已自动补全为: {url}")
            
            # 🛡️ 未替换变量提前检测 (Safety Net)
            unreplaced = re.findall(r'\$\{(\w+)\}', url)
            if unreplaced:
                available = list(active_context.keys())
                error_msg = (
                    f"变量注入失败: URL 中存在未替换的变量 {unreplaced}。"
                    f"context_pool 可用变量: {available}。"
                    f"上游 extract 命名与下游 ${{var_name}} 不一致。"
                )
                logger.error(f"🛡️ {error_msg}")
                return ExecutionResult(
                    success=False,
                    response=None,
                    assertions_passed=[],
                    assertions_failed=[error_msg],
                    extracted_values={},
                    error=error_msg,
                )
            
            logger.info(f"执行 API: {api_ir.method} {url}")
            logger.debug(f"Headers: {headers}")
            if body:
                logger.debug(f"Body: {body}")
            
            # 2. 发送请求
            if not self._client:
                self._client = httpx.AsyncClient(timeout=self.timeout, trust_env=False)
            
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
            
            if extracted:
                active_context.update(extracted)
                # Ensure we also update internal context if context wasn't passed (backward compat)
                if context is None:
                    self._context.update(extracted)
                
                for k, v in extracted.items():
                    logger.info(f"🧬 成功提取变量: {k} = {v}")
            
            
            # 5. 断言验证
            from app.engines.left_pupil.assertion_engine import AssertionEngine
            assertion_engine = AssertionEngine()
            
            # --- Strict Assertion Enforcement (Anti-Hallucination) ---
            # 1. 如果指定了 expected_status_code，严格校验
            # 2. 如果没指定，默认校验 2xx
            # 3. 任何状态码不匹配直接视为 Failed，并记录 reason
            
            expected_code = getattr(api_ir, "expected_status_code", None)
            json_assertions = getattr(api_ir, "json_assertions", {})
            logger.error(f"👀 [Check 3] API Executor 准备校验! 获取到的 expected_code: {expected_code}, json_asserts: {json_assertions}")
            
            actual_code = api_response.status_code
            
            status_error = None
            
            if expected_code is not None:
                # Case A: Strict Match
                if actual_code != expected_code:
                    status_error = f"Status Code Mismatch: Expected {expected_code}, got {actual_code}"
            else:
                # Case B: Implicit Success (Default 2xx)
                # Only check if NO explicit status_code assertion exists in validation rules
                has_explicit_status_rule = any(a.get("type") == "status_code" for a in api_ir.assertions)
                if not has_explicit_status_rule:
                    if not (200 <= actual_code < 300):
                        status_error = f"HTTP Status Error: Expected 2xx, got {actual_code} (Implicit Rule)"

            if status_error:
                logger.warning(f"Strict Assertion Failed: {status_error}")
                # Inject a failure into the results
                # We do this by creating a synthetic failed assertion result
                # actual assertion engine run might still pass if it checks nothing relevant
                pass # Logic handled below by appending to failures
            # -----------------------------------------------------

            # --- Deep JSON Body Verification ---
            deep_json_failures = []
            json_assertions = getattr(api_ir, "json_assertions", {})
            if json_assertions:
                try:
                    # 获取响应 JSON
                    resp_json = api_response.body
                    if isinstance(resp_json, str):
                        import json
                        try:
                            resp_json = json.loads(resp_json)
                        except:
                            pass # Keep as string if not JSON

                    if isinstance(resp_json, dict) or isinstance(resp_json, list):
                        for key, expected_value in json_assertions.items():
                            # TODO: Support JSONPath (jsonpath-ng) for nested keys
                            # Current MVP: Direct key match or simple dot notation for 1-level depth
                            actual_value = None
                            
                            # Simple Dict Access
                            if isinstance(resp_json, dict):
                                actual_value = resp_json.get(key)
                                # Support "data.id" style for simple depth
                                if actual_value is None and "." in key:
                                    parts = key.split(".")
                                    temp = resp_json
                                    for p in parts:
                                        if isinstance(temp, dict):
                                            temp = temp.get(p)
                                        else:
                                            temp = None
                                            break
                                    actual_value = temp
                            
                            # Comparison
                            # Convert both to string for loose comparison if types differ
                            if str(actual_value) != str(expected_value):
                                fail_msg = f"JSON Mismatch at '{key}': Expected '{expected_value}', got '{actual_value}'"
                                logger.warning(fail_msg)
                                deep_json_failures.append(fail_msg)
                    else:
                         deep_json_failures.append(f"Body Assertion Failed: Expected JSON structure, got {type(resp_json)}")

                except Exception as e:
                    err_msg = f"Deep JSON Assertion Error: {str(e)}"
                    logger.error(err_msg)
                    deep_json_failures.append(err_msg)
            # -----------------------------------------------------

            assertion_result = assertion_engine.run_assertions(
                api_ir.assertions,
                api_response,
            )
            
            # Merge Strict Status Error
            if status_error:
                assertion_result["failed"].insert(0, status_error)
            
            # Merge Deep JSON Failures
            if deep_json_failures:
                assertion_result["failed"].extend(deep_json_failures)
            
            success = len(assertion_result["failed"]) == 0
            
            return ExecutionResult(
                success=success,
                response=api_response,
                assertions_passed=assertion_result["passed"],
                assertions_failed=assertion_result["failed"],
                extracted_values=extracted,
            )
            
        except httpx.TimeoutException as e:
            logger.error(f"API 请求超时: {url} - {e}")
            return ExecutionResult(
                success=False,
                response=None,
                assertions_passed=[],
                assertions_failed=[],
                extracted_values={},
                error=f"Timeout: {str(e)}",
            )
        except httpx.ConnectError as e:
            logger.error(f"API 连接失败: {url} - {e}")
            return ExecutionResult(
                success=False,
                response=None,
                assertions_passed=[],
                assertions_failed=[],
                extracted_values={},
                error=f"Connection Error: {str(e)}",
            )
        except httpx.HTTPStatusError as e:
            # Note: We usually don't raise on status code unless configured, 
            # but httpx raises if .raise_for_status() is called. 
            # Here we just catch it in case.
            logger.error(f"HTTP 状态错误: {e}")
            return ExecutionResult(
                success=False,
                response=None,
                assertions_passed=[],
                assertions_failed=[],
                extracted_values={},
                error=f"HTTP Error: {str(e)}",
            )
        except Exception as e:
            logger.error(f"API 执行未知错误: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            error_msg = f"执行错误: {str(e)}"
            return ExecutionResult(
                success=False,
                response=None,
                assertions_passed=[],
                assertions_failed=[error_msg],
                extracted_values={},
                error=error_msg,
            )
    
    def _build_headers(self, api_ir: APIIR, context: Dict[str, Any]) -> Dict[str, str]:
        """构建请求头"""
        headers = {**self.default_headers, **api_ir.headers}
        
        # Content-Type
        if api_ir.body and "Content-Type" not in headers:
            headers["Content-Type"] = api_ir.content_type
        
        # 认证
        if self.auth_config.auth_type == AuthType.BEARER:
            token = self._replace_variables(self.auth_config.token, context)
            headers["Authorization"] = f"Bearer {token}"
        
        elif self.auth_config.auth_type == AuthType.BASIC:
            import base64
            username = self._replace_variables(self.auth_config.username, context)
            password = self._replace_variables(self.auth_config.password, context)
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        
        elif self.auth_config.auth_type == AuthType.API_KEY:
            if self.auth_config.api_key_location == "header":
                headers[self.auth_config.api_key_name] = self._replace_variables(self.auth_config.api_key_value, context)
        
        # 变量替换
        final_headers = {k: self._replace_variables(v, context) for k, v in headers.items()}
        
        # 🚀 破除 403 魔咒：注入反爬虫伪装面具
        # Check if user-agent exists (case-insensitive)
        if "user-agent" not in {k.lower() for k in final_headers}:
            final_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
        return final_headers
    
    def _replace_variables(self, text: str, context: Dict[str, Any]) -> str:
        """替换变量占位符 ${variable}"""
        if not isinstance(text, str):
            return text
        
        pattern = r'\$\{(\w+)\}'
        
        def replacer(match):
            var_name = match.group(1)
            val = context.get(var_name)
            if val is None:
                val = self._context.get(var_name)
            if val is None:
                logger.warning(
                    f"⚠️ 变量 ${{{var_name}}} 未在 context_pool 中找到! "
                    f"可用变量: {list(context.keys())}"
                )
                return match.group(0)  # 原样返回
            return str(val)
        
        return re.sub(pattern, replacer, text)
    
    def _replace_path_params(self, url: str, path_params: Dict[str, Any], context: Dict[str, Any]) -> str:
        """替换路径参数 {param}"""
        for name, value in path_params.items():
            url = url.replace(f"{{{name}}}", str(self._replace_variables(str(value), context)))
        return url
    
    def _replace_variables_in_obj(self, obj: Any, context: Dict[str, Any]) -> Any:
        """递归替换对象中的变量"""
        if isinstance(obj, str):
            return self._replace_variables(obj, context)
        elif isinstance(obj, dict):
            return {k: self._replace_variables_in_obj(v, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_variables_in_obj(item, context) for item in obj]
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
