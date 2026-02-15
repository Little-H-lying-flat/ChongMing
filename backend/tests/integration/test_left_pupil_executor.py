
import pytest
import pytest
from app.engines.left_pupil.api_executor import APIExecutor
from app.schemas.api_ir import APIIR, AuthConfig, AuthType

@pytest.mark.asyncio
async def test_execute_simple_get():
    """Test executing a simple GET request"""
    # Using httpbin.org for testing
    api_ir = APIIR(
        method="GET",
        url="https://httpbin.org/get",
        headers={"User-Agent": "TestExecutor"},
        assertions=[{"type": "status_code", "expected": 200}]
    )
    
    async with APIExecutor() as executor:
        result = await executor.execute(api_ir)
        
        assert result.success is True
        assert result.response.status_code == 200
        # httpx/httpbin returns lowercase headers in dict(response.headers)
        assert result.response.headers.get("content-type") == "application/json"
        
@pytest.mark.asyncio
async def test_execute_post_with_body():
    """Test executing a POST request with JSON body"""
    payload = {"key": "value", "id": 123}
    api_ir = APIIR(
        method="POST",
        url="https://httpbin.org/post",
        body=payload,
        content_type="application/json",
        assertions=[
            {"type": "status_code", "expected": 200},
            {"type": "jsonpath", "path": "$.json.key", "expected": "value"}
        ]
    )
    
    async with APIExecutor() as executor:
        result = await executor.execute(api_ir)
        
        assert result.success is True
        assert result.response.status_code == 200
        # Check if response body contains our payload (httpbin echoes it)
        assert result.response.body["json"]["key"] == "value"

@pytest.mark.asyncio
async def test_variable_substitution():
    """Test variable substitution in URL (path) and Headers"""
    api_ir = APIIR(
        method="GET",
        # Use path variable to avoid query param stripping issues with httpx/httpbin
        url="https://httpbin.org/anything/${path_var}",
        headers={"X-Custom-Header": "${header_val}"},
        assertions=[
            {"type": "status_code", "expected": 200},
            {"type": "jsonpath", "path": "$.url", "expected": "https://httpbin.org/anything/test_path", "operator": "contains"},
            {"type": "jsonpath", "path": "$.headers.X-Custom-Header", "expected": "test_header"}
        ]
    )
    
    async with APIExecutor() as executor:
        executor.set_context("path_var", "test_path")
        executor.set_context("header_val", "test_header")
        
        result = await executor.execute(api_ir)
        
        if not result.success:
            print(f"FAILED: {result.assertions_failed}")
            print(f"BODY: {result.response.body}")
        
        assert result.success is True
        
@pytest.mark.asyncio
async def test_extraction():
    """Test extracting values from response"""
    api_ir = APIIR(
        method="GET",
        url="https://httpbin.org/json", # Returns a sample slideshow json
        extract={
            "author": "$.slideshow.author",
            "date": "$.slideshow.date"
        },
        assertions=[{"type": "status_code", "expected": 200}]
    )
    
    async with APIExecutor() as executor:
        result = await executor.execute(api_ir)
        
        assert result.success is True
        # Check context for extracted values
        assert executor.get_context("author") == "Yours Truly"
        assert "date" in result.extracted_values

@pytest.mark.asyncio
async def test_auth_bearer():
    """Test Bearer Token Injection"""
    auth = AuthConfig(auth_type=AuthType.BEARER, token="secret_token")
    api_ir = APIIR(
        method="GET",
        url="https://httpbin.org/bearer",
        assertions=[{"type": "status_code", "expected": 200}]
    )
    
    async with APIExecutor(auth_config=auth) as executor:
        result = await executor.execute(api_ir)
        
        # httpbin/bearer checks Authorization header
        assert result.success is True
        assert result.response.status_code == 200
