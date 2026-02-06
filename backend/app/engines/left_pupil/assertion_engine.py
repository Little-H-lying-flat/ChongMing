"""
断言引擎

API 响应断言验证
对应 Issue: #LP-004
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re
import json

from loguru import logger

from app.engines.left_pupil.variable_extractor import VariableExtractor


@dataclass
class AssertionResult:
    """断言结果"""
    assertion_type: str
    expected: Any
    actual: Any
    passed: bool
    message: str


class AssertionEngine:
    """
    断言引擎
    
    支持的断言类型:
    - status_code: 状态码断言
    - jsonpath: JSONPath 值断言
    - schema: JSON Schema 断言
    - response_time: 响应时间断言
    - contains: 包含断言
    - regex: 正则匹配断言
    - header: 响应头断言
    """
    
    def __init__(self):
        self._extractor = VariableExtractor()
        
        # 断言处理器映射
        self._handlers = {
            "status_code": self._assert_status_code,
            "jsonpath": self._assert_jsonpath,
            "contains": self._assert_contains,
            "not_contains": self._assert_not_contains,
            "equals": self._assert_equals,
            "not_equals": self._assert_not_equals,
            "regex": self._assert_regex,
            "header": self._assert_header,
            "response_time": self._assert_response_time,
            "schema": self._assert_schema,
            "length": self._assert_length,
            "type": self._assert_type,
            "gt": self._assert_greater_than,
            "gte": self._assert_greater_equal,
            "lt": self._assert_less_than,
            "lte": self._assert_less_equal,
        }
    
    def run_assertions(
        self,
        assertions: List[Dict],
        response: "APIResponse",
    ) -> Dict[str, List[str]]:
        """
        运行所有断言
        
        Args:
            assertions: 断言列表
            response: API 响应
            
        Returns:
            {"passed": [...], "failed": [...]}
        """
        passed = []
        failed = []
        
        for assertion in assertions:
            result = self.run_single(assertion, response)
            
            if result.passed:
                passed.append(result.message)
                logger.debug(f"✅ 断言通过: {result.message}")
            else:
                failed.append(result.message)
                logger.warning(f"❌ 断言失败: {result.message}")
        
        return {"passed": passed, "failed": failed}
    
    def run_single(self, assertion: Dict, response: "APIResponse") -> AssertionResult:
        """
        运行单个断言
        
        Args:
            assertion: 断言配置
            response: API 响应
            
        Returns:
            AssertionResult: 断言结果
        """
        assertion_type = assertion.get("type", "status_code")
        handler = self._handlers.get(assertion_type)
        
        if not handler:
            return AssertionResult(
                assertion_type=assertion_type,
                expected=None,
                actual=None,
                passed=False,
                message=f"未知的断言类型: {assertion_type}",
            )
        
        try:
            return handler(assertion, response)
        except Exception as e:
            return AssertionResult(
                assertion_type=assertion_type,
                expected=assertion.get("expected"),
                actual=None,
                passed=False,
                message=f"断言执行异常: {str(e)}",
            )
    
    def _assert_status_code(self, assertion: Dict, response) -> AssertionResult:
        """状态码断言"""
        expected = assertion.get("expected", 200)
        actual = response.status_code
        
        # 支持多个状态码
        if isinstance(expected, list):
            passed = actual in expected
        else:
            passed = actual == expected
        
        return AssertionResult(
            assertion_type="status_code",
            expected=expected,
            actual=actual,
            passed=passed,
            message=f"状态码: 期望 {expected}, 实际 {actual}",
        )
    
    def _assert_jsonpath(self, assertion: Dict, response) -> AssertionResult:
        """JSONPath 断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected")
        operator = assertion.get("operator", "equals")
        
        actual = self._extractor.extract(response.body, path)
        
        # 根据操作符比较
        if operator == "equals":
            passed = actual == expected
        elif operator == "contains":
            passed = expected in str(actual) if actual else False
        elif operator == "exists":
            passed = actual is not None
        elif operator == "not_exists":
            passed = actual is None
        else:
            passed = actual == expected
        
        return AssertionResult(
            assertion_type="jsonpath",
            expected=expected,
            actual=actual,
            passed=passed,
            message=f"JSONPath {path}: 期望 {expected}, 实际 {actual}",
        )
    
    def _assert_contains(self, assertion: Dict, response) -> AssertionResult:
        """包含断言"""
        expected = assertion.get("expected", "")
        target = assertion.get("target", "body")
        
        if target == "body":
            actual = str(response.body)
        else:
            actual = str(response.raw_body)
        
        passed = expected in actual
        
        return AssertionResult(
            assertion_type="contains",
            expected=expected,
            actual=f"[响应体 {len(actual)} 字符]",
            passed=passed,
            message=f"包含检查: '{expected}' {'存在' if passed else '不存在'}",
        )
    
    def _assert_not_contains(self, assertion: Dict, response) -> AssertionResult:
        """不包含断言"""
        expected = assertion.get("expected", "")
        actual = str(response.body)
        
        passed = expected not in actual
        
        return AssertionResult(
            assertion_type="not_contains",
            expected=f"不包含 '{expected}'",
            actual=f"[响应体]",
            passed=passed,
            message=f"不包含检查: '{expected}' {'不存在' if passed else '存在'}",
        )
    
    def _assert_equals(self, assertion: Dict, response) -> AssertionResult:
        """相等断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected")
        
        actual = self._extractor.extract(response.body, path)
        passed = actual == expected
        
        return AssertionResult(
            assertion_type="equals",
            expected=expected,
            actual=actual,
            passed=passed,
            message=f"相等: {path} = {expected}, 实际 {actual}",
        )
    
    def _assert_not_equals(self, assertion: Dict, response) -> AssertionResult:
        """不相等断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected")
        
        actual = self._extractor.extract(response.body, path)
        passed = actual != expected
        
        return AssertionResult(
            assertion_type="not_equals",
            expected=f"!= {expected}",
            actual=actual,
            passed=passed,
            message=f"不相等: {path} != {expected}, 实际 {actual}",
        )
    
    def _assert_regex(self, assertion: Dict, response) -> AssertionResult:
        """正则匹配断言"""
        pattern = assertion.get("pattern", "")
        target = assertion.get("target", "body")
        
        if target == "body":
            actual = str(response.body)
        else:
            actual = response.headers.get(target, "")
        
        passed = bool(re.search(pattern, actual))
        
        return AssertionResult(
            assertion_type="regex",
            expected=pattern,
            actual=f"[匹配: {passed}]",
            passed=passed,
            message=f"正则匹配: {pattern} {'匹配' if passed else '不匹配'}",
        )
    
    def _assert_header(self, assertion: Dict, response) -> AssertionResult:
        """响应头断言"""
        header_name = assertion.get("name", "")
        expected = assertion.get("expected")
        
        actual = response.headers.get(header_name)
        passed = actual == expected
        
        return AssertionResult(
            assertion_type="header",
            expected=expected,
            actual=actual,
            passed=passed,
            message=f"响应头 {header_name}: 期望 {expected}, 实际 {actual}",
        )
    
    def _assert_response_time(self, assertion: Dict, response) -> AssertionResult:
        """响应时间断言"""
        max_ms = assertion.get("max", 1000)
        actual = response.duration_ms
        
        passed = actual <= max_ms
        
        return AssertionResult(
            assertion_type="response_time",
            expected=f"<= {max_ms}ms",
            actual=f"{actual:.2f}ms",
            passed=passed,
            message=f"响应时间: {actual:.2f}ms {'<=' if passed else '>'} {max_ms}ms",
        )
    
    def _assert_schema(self, assertion: Dict, response) -> AssertionResult:
        """JSON Schema 断言"""
        schema = assertion.get("schema", {})
        
        # 简化的 Schema 验证
        # 完整实现可使用 jsonschema 库
        try:
            self._validate_schema(response.body, schema)
            passed = True
            message = "Schema 验证通过"
        except Exception as e:
            passed = False
            message = f"Schema 验证失败: {e}"
        
        return AssertionResult(
            assertion_type="schema",
            expected="[Schema]",
            actual="[响应体]",
            passed=passed,
            message=message,
        )
    
    def _validate_schema(self, data: Any, schema: Dict):
        """简化的 Schema 验证"""
        schema_type = schema.get("type")
        
        if schema_type == "object":
            if not isinstance(data, dict):
                raise ValueError(f"期望 object, 实际 {type(data).__name__}")
            
            # 验证必需字段
            required = schema.get("required", [])
            for field in required:
                if field not in data:
                    raise ValueError(f"缺少必需字段: {field}")
        
        elif schema_type == "array":
            if not isinstance(data, list):
                raise ValueError(f"期望 array, 实际 {type(data).__name__}")
        
        elif schema_type == "string":
            if not isinstance(data, str):
                raise ValueError(f"期望 string, 实际 {type(data).__name__}")
        
        elif schema_type == "number":
            if not isinstance(data, (int, float)):
                raise ValueError(f"期望 number, 实际 {type(data).__name__}")
    
    def _assert_length(self, assertion: Dict, response) -> AssertionResult:
        """长度断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected")
        operator = assertion.get("operator", "equals")
        
        actual_value = self._extractor.extract(response.body, path)
        actual = len(actual_value) if actual_value else 0
        
        if operator == "equals":
            passed = actual == expected
        elif operator == "gt":
            passed = actual > expected
        elif operator == "gte":
            passed = actual >= expected
        elif operator == "lt":
            passed = actual < expected
        elif operator == "lte":
            passed = actual <= expected
        else:
            passed = actual == expected
        
        return AssertionResult(
            assertion_type="length",
            expected=f"{operator} {expected}",
            actual=actual,
            passed=passed,
            message=f"长度: {path} = {actual}, 期望 {operator} {expected}",
        )
    
    def _assert_type(self, assertion: Dict, response) -> AssertionResult:
        """类型断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected", "string")
        
        actual_value = self._extractor.extract(response.body, path)
        actual_type = type(actual_value).__name__
        
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        
        expected_type = type_mapping.get(expected)
        passed = isinstance(actual_value, expected_type) if expected_type else False
        
        return AssertionResult(
            assertion_type="type",
            expected=expected,
            actual=actual_type,
            passed=passed,
            message=f"类型: {path} = {actual_type}, 期望 {expected}",
        )
    
    def _assert_greater_than(self, assertion: Dict, response) -> AssertionResult:
        """大于断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected", 0)
        
        actual = self._extractor.extract(response.body, path)
        passed = actual > expected if actual is not None else False
        
        return AssertionResult(
            assertion_type="gt",
            expected=f"> {expected}",
            actual=actual,
            passed=passed,
            message=f"大于: {path} = {actual} > {expected}",
        )
    
    def _assert_greater_equal(self, assertion: Dict, response) -> AssertionResult:
        """大于等于断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected", 0)
        
        actual = self._extractor.extract(response.body, path)
        passed = actual >= expected if actual is not None else False
        
        return AssertionResult(
            assertion_type="gte",
            expected=f">= {expected}",
            actual=actual,
            passed=passed,
            message=f"大于等于: {path} = {actual} >= {expected}",
        )
    
    def _assert_less_than(self, assertion: Dict, response) -> AssertionResult:
        """小于断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected", 0)
        
        actual = self._extractor.extract(response.body, path)
        passed = actual < expected if actual is not None else False
        
        return AssertionResult(
            assertion_type="lt",
            expected=f"< {expected}",
            actual=actual,
            passed=passed,
            message=f"小于: {path} = {actual} < {expected}",
        )
    
    def _assert_less_equal(self, assertion: Dict, response) -> AssertionResult:
        """小于等于断言"""
        path = assertion.get("path", "$")
        expected = assertion.get("expected", 0)
        
        actual = self._extractor.extract(response.body, path)
        passed = actual <= expected if actual is not None else False
        
        return AssertionResult(
            assertion_type="lte",
            expected=f"<= {expected}",
            actual=actual,
            passed=passed,
            message=f"小于等于: {path} = {actual} <= {expected}",
        )
