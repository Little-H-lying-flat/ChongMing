"""
响应断言器

验证 API 响应的正确性
"""

import re
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# 尝试导入 jsonpath-ng，如果没有则使用简单实现
try:
    from jsonpath_ng import parse as jsonpath_parse
    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False


class AssertionType(Enum):
    """断言类型"""
    STATUS_CODE = "status_code"
    JSON_PATH = "json_path"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    REGEX = "regex"
    SCHEMA = "schema"
    EXPRESSION = "expression"


@dataclass
class AssertionRule:
    """单条断言规则"""
    type: AssertionType
    expected: Any
    path: str = ""  # JsonPath 路径
    message: str = ""  # 自定义错误消息


@dataclass
class AssertionResult:
    """断言结果"""
    passed: bool
    rule_type: str
    expected: Any
    actual: Any = None
    message: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "passed": self.passed,
            "rule_type": self.rule_type,
            "expected": str(self.expected) if self.expected is not None else None,
            "actual": str(self.actual) if self.actual is not None else None,
            "message": self.message,
        }


@dataclass
class AssertionReport:
    """断言报告"""
    passed: bool
    results: list[AssertionResult] = field(default_factory=list)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "passed": self.passed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "results": [r.to_dict() for r in self.results],
        }


class Asserter:
    """
    响应断言器
    
    支持多种断言方式：
    - 状态码断言
    - JsonPath 断言
    - 内容包含/不包含
    - 正则表达式
    - 自定义表达式
    """
    
    def assert_all(
        self,
        response_data: dict,
        rules: list[AssertionRule],
        status_code: Optional[int] = None,
    ) -> AssertionReport:
        """
        执行所有断言
        
        Args:
            response_data: 响应数据
            rules: 断言规则列表
            status_code: HTTP 状态码
        
        Returns:
            断言报告
        """
        results = []
        
        for rule in rules:
            result = self._assert_one(rule, response_data, status_code)
            results.append(result)
        
        return AssertionReport(
            passed=all(r.passed for r in results),
            results=results,
        )
    
    def _assert_one(
        self,
        rule: AssertionRule,
        response_data: dict,
        status_code: Optional[int],
    ) -> AssertionResult:
        """执行单条断言"""
        try:
            if rule.type == AssertionType.STATUS_CODE:
                return self._assert_status_code(rule, status_code)
            elif rule.type == AssertionType.JSON_PATH:
                return self._assert_json_path(rule, response_data)
            elif rule.type == AssertionType.CONTAINS:
                return self._assert_contains(rule, response_data)
            elif rule.type == AssertionType.NOT_CONTAINS:
                return self._assert_not_contains(rule, response_data)
            elif rule.type == AssertionType.REGEX:
                return self._assert_regex(rule, response_data)
            elif rule.type == AssertionType.EXPRESSION:
                return self._assert_expression(rule, response_data)
            else:
                return AssertionResult(
                    passed=False,
                    rule_type=rule.type.value,
                    expected=rule.expected,
                    message=f"不支持的断言类型: {rule.type}",
                )
        except Exception as e:
            return AssertionResult(
                passed=False,
                rule_type=rule.type.value,
                expected=rule.expected,
                message=f"断言执行错误: {str(e)}",
            )
    
    def _assert_status_code(
        self,
        rule: AssertionRule,
        status_code: Optional[int],
    ) -> AssertionResult:
        """状态码断言"""
        expected = rule.expected
        
        # 支持单个值或列表
        if isinstance(expected, int):
            passed = status_code == expected
        elif isinstance(expected, list):
            passed = status_code in expected
        else:
            passed = str(status_code) == str(expected)
        
        return AssertionResult(
            passed=passed,
            rule_type="status_code",
            expected=expected,
            actual=status_code,
            message="" if passed else f"状态码不匹配: 期望 {expected}, 实际 {status_code}",
        )
    
    def _assert_json_path(
        self,
        rule: AssertionRule,
        response_data: dict,
    ) -> AssertionResult:
        """JsonPath 断言"""
        path = rule.path
        expected = rule.expected
        
        actual = self._extract_json_path(response_data, path)
        
        # 特殊断言
        if isinstance(expected, dict):
            if expected.get("type") == "not_null":
                passed = actual is not None
                message = "" if passed else f"字段 {path} 为空"
            elif expected.get("type") == "exists":
                passed = actual is not None
                message = "" if passed else f"字段 {path} 不存在"
            elif expected.get("type") == "gt":
                passed = actual is not None and actual > expected.get("value", 0)
                message = "" if passed else f"{path} 应大于 {expected.get('value')}"
            elif expected.get("type") == "lt":
                passed = actual is not None and actual < expected.get("value", 0)
                message = "" if passed else f"{path} 应小于 {expected.get('value')}"
            else:
                passed = actual == expected
                message = "" if passed else f"JsonPath 不匹配: {path}"
        else:
            passed = actual == expected
            message = "" if passed else f"JsonPath 不匹配: 期望 {expected}, 实际 {actual}"
        
        return AssertionResult(
            passed=passed,
            rule_type="json_path",
            expected=expected,
            actual=actual,
            message=message,
        )
    
    def _extract_json_path(self, data: dict, path: str) -> Any:
        """提取 JsonPath 值"""
        if HAS_JSONPATH:
            try:
                expr = jsonpath_parse(path)
                matches = expr.find(data)
                if matches:
                    return matches[0].value
            except Exception:
                pass
        
        # 简单实现 (支持 $.a.b.c 格式)
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
    
    def _assert_contains(
        self,
        rule: AssertionRule,
        response_data: dict,
    ) -> AssertionResult:
        """内容包含断言"""
        expected = rule.expected
        text = str(response_data)
        
        passed = expected in text
        return AssertionResult(
            passed=passed,
            rule_type="contains",
            expected=expected,
            message="" if passed else f"响应不包含: {expected}",
        )
    
    def _assert_not_contains(
        self,
        rule: AssertionRule,
        response_data: dict,
    ) -> AssertionResult:
        """内容不包含断言"""
        expected = rule.expected
        text = str(response_data)
        
        passed = expected not in text
        return AssertionResult(
            passed=passed,
            rule_type="not_contains",
            expected=expected,
            message="" if passed else f"响应不应包含: {expected}",
        )
    
    def _assert_regex(
        self,
        rule: AssertionRule,
        response_data: dict,
    ) -> AssertionResult:
        """正则表达式断言"""
        pattern = rule.expected
        text = str(response_data)
        
        try:
            passed = bool(re.search(pattern, text))
        except re.error:
            passed = False
        
        return AssertionResult(
            passed=passed,
            rule_type="regex",
            expected=pattern,
            message="" if passed else f"正则不匹配: {pattern}",
        )
    
    def _assert_expression(
        self,
        rule: AssertionRule,
        response_data: dict,
    ) -> AssertionResult:
        """自定义表达式断言"""
        expression = rule.expected
        
        # 安全沙箱执行
        try:
            # 提供有限的上下文
            # 支持数组和对象两种响应类型
            data_value = {}
            if isinstance(response_data, dict):
                data_value = response_data.get("data", {})
            
            context = {
                "response": response_data,
                "data": data_value,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "isinstance": isinstance,
                "list": list,
                "dict": dict,
            }
            
            passed = bool(eval(expression, {"__builtins__": {}}, context))
        except Exception as e:
            passed = False
            return AssertionResult(
                passed=False,
                rule_type="expression",
                expected=expression,
                message=f"表达式执行错误: {str(e)}",
            )
        
        return AssertionResult(
            passed=passed,
            rule_type="expression",
            expected=expression,
            message="" if passed else f"表达式断言失败: {expression}",
        )


def create_rules_from_dict(config: dict) -> list[AssertionRule]:
    """
    从字典配置创建断言规则
    
    配置格式:
    {
        "status_code": 200,
        "json_assertions": {
            "$.data.status": "success",
            "$.data.id": {"type": "not_null"}
        },
        "contains": "success",
        "expression": "len(data.items) > 0"
    }
    """
    rules = []
    
    # 状态码
    if "status_code" in config:
        rules.append(AssertionRule(
            type=AssertionType.STATUS_CODE,
            expected=config["status_code"],
        ))
    
    # JsonPath
    for path, expected in config.get("json_assertions", {}).items():
        rules.append(AssertionRule(
            type=AssertionType.JSON_PATH,
            path=path,
            expected=expected,
        ))
    
    # 包含
    if "contains" in config:
        rules.append(AssertionRule(
            type=AssertionType.CONTAINS,
            expected=config["contains"],
        ))
    
    # 不包含
    if "not_contains" in config:
        rules.append(AssertionRule(
            type=AssertionType.NOT_CONTAINS,
            expected=config["not_contains"],
        ))
    
    # 正则
    if "regex" in config:
        rules.append(AssertionRule(
            type=AssertionType.REGEX,
            expected=config["regex"],
        ))
    
    # 表达式
    if "expression" in config:
        rules.append(AssertionRule(
            type=AssertionType.EXPRESSION,
            expected=config["expression"],
        ))
    
    return rules
