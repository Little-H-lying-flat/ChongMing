
import pytest
import pytest
from app.engines.left_pupil.assertion_engine import AssertionEngine
from app.schemas.api_ir import APIResponse

@pytest.fixture
def sample_response():
    return APIResponse(
        status_code=200,
        headers={"Content-Type": "application/json", "X-ID": "123"},
        body={
            "user": {
                "id": 1,
                "name": "Alice",
                "roles": ["admin", "editor"]
            },
            "status": "active",
            "score": 95.5
        },
        raw_body=b'{"user": ...}', # Simplified
        duration_ms=150,
        request_url="http://test.com",
        request_method="GET"
    )

def test_assert_status_code(sample_response):
    engine = AssertionEngine()
    
    # Pass
    res = engine.run_single({"type": "status_code", "expected": 200}, sample_response)
    assert res.passed is True
    
    # Fail
    res = engine.run_single({"type": "status_code", "expected": 404}, sample_response)
    assert res.passed is False

def test_assert_jsonpath(sample_response):
    engine = AssertionEngine()
    
    # Equals
    res = engine.run_single(
        {"type": "jsonpath", "path": "$.user.name", "expected": "Alice"}, 
        sample_response
    )
    assert res.passed is True
    
    # Contains (in Array)
    res = engine.run_single(
        {"type": "jsonpath", "path": "$.user.roles", "expected": "admin", "operator": "contains"}, 
        sample_response
    )
    assert res.passed is True

def test_assert_header(sample_response):
    engine = AssertionEngine()
    
    res = engine.run_single(
        {"type": "header", "name": "X-ID", "expected": "123"}, 
        sample_response
    )
    assert res.passed is True

def test_assert_greater_than(sample_response):
    engine = AssertionEngine()
    
    res = engine.run_single(
        {"type": "gt", "path": "$.score", "expected": 90}, 
        sample_response
    )
    assert res.passed is True

def test_run_assertions_batch(sample_response):
    engine = AssertionEngine()
    
    assertions = [
        {"type": "status_code", "expected": 200},
        {"type": "jsonpath", "path": "$.status", "expected": "active"},
        {"type": "lt", "path": "$.score", "expected": 100}
    ]
    
    result = engine.run_assertions(assertions, sample_response)
    
    assert len(result["passed"]) == 3
    assert len(result["failed"]) == 0
