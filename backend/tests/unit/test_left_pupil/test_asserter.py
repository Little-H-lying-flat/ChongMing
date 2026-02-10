"""
断言器单元测试
"""

import pytest
from app.services.left_pupil.asserter import (
    Asserter, AssertionType, AssertionRule, create_rules_from_dict
)


class TestAsserter:
    """Asserter 测试"""
    
    @pytest.fixture
    def asserter(self):
        return Asserter()
    
    def test_status_code_pass(self, asserter):
        """测试状态码断言通过"""
        rule = AssertionRule(
            type=AssertionType.STATUS_CODE,
            expected=200,
        )
        
        report = asserter.assert_all({}, [rule], status_code=200)
        
        assert report.passed
        assert report.passed_count == 1
    
    def test_status_code_fail(self, asserter):
        """测试状态码断言失败"""
        rule = AssertionRule(
            type=AssertionType.STATUS_CODE,
            expected=200,
        )
        
        report = asserter.assert_all({}, [rule], status_code=500)
        
        assert not report.passed
        assert report.failed_count == 1
    
    def test_status_code_list(self, asserter):
        """测试状态码列表断言"""
        rule = AssertionRule(
            type=AssertionType.STATUS_CODE,
            expected=[200, 201, 204],
        )
        
        report = asserter.assert_all({}, [rule], status_code=201)
        
        assert report.passed
    
    def test_json_path_equal(self, asserter):
        """测试 JsonPath 相等断言"""
        rule = AssertionRule(
            type=AssertionType.JSON_PATH,
            path="$.data.status",
            expected="success",
        )
        
        response = {"data": {"status": "success"}}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_json_path_nested(self, asserter):
        """测试嵌套 JsonPath"""
        rule = AssertionRule(
            type=AssertionType.JSON_PATH,
            path="$.data.user.id",
            expected=123,
        )
        
        response = {"data": {"user": {"id": 123}}}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_json_path_not_null(self, asserter):
        """测试非空断言"""
        rule = AssertionRule(
            type=AssertionType.JSON_PATH,
            path="$.data.token",
            expected={"type": "not_null"},
        )
        
        response = {"data": {"token": "abc123"}}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_json_path_gt(self, asserter):
        """测试大于断言"""
        rule = AssertionRule(
            type=AssertionType.JSON_PATH,
            path="$.data.count",
            expected={"type": "gt", "value": 0},
        )
        
        response = {"data": {"count": 5}}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_contains_pass(self, asserter):
        """测试包含断言通过"""
        rule = AssertionRule(
            type=AssertionType.CONTAINS,
            expected="success",
        )
        
        response = {"message": "Operation success"}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_not_contains_pass(self, asserter):
        """测试不包含断言通过"""
        rule = AssertionRule(
            type=AssertionType.NOT_CONTAINS,
            expected="error",
        )
        
        response = {"message": "Operation success"}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_regex_match(self, asserter):
        """测试正则匹配"""
        rule = AssertionRule(
            type=AssertionType.REGEX,
            expected=r"\d{3}-\d{4}",
        )
        
        response = {"phone": "123-4567"}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_expression_pass(self, asserter):
        """测试表达式断言通过"""
        rule = AssertionRule(
            type=AssertionType.EXPRESSION,
            expected="len(data.get('items', [])) > 0",
        )
        
        response = {"data": {"items": [1, 2, 3]}}
        report = asserter.assert_all(response, [rule])
        
        assert report.passed
    
    def test_multiple_rules(self, asserter):
        """测试多条规则"""
        rules = [
            AssertionRule(type=AssertionType.STATUS_CODE, expected=200),
            AssertionRule(
                type=AssertionType.JSON_PATH,
                path="$.success",
                expected=True,
            ),
            AssertionRule(
                type=AssertionType.CONTAINS,
                expected="ok",
            ),
        ]
        
        response = {"success": True, "message": "ok"}
        report = asserter.assert_all(response, rules, status_code=200)
        
        assert report.passed
        assert report.passed_count == 3
    
    def test_create_rules_from_dict(self):
        """测试从字典创建规则"""
        config = {
            "status_code": 200,
            "json_assertions": {
                "$.data.id": {"type": "not_null"},
                "$.success": True,
            },
            "contains": "success",
        }
        
        rules = create_rules_from_dict(config)
        
        assert len(rules) == 4  # 1 status + 2 json + 1 contains
