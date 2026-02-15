import pytest
import respx
from httpx import Response
from app.engines.left_pupil.api_executor import APIExecutor
from app.schemas.api_ir import APIIR

# Need to ensure assertions are recognized
# The engine uses AssertionEngine, which we should also trust or mock if needed.
# But for E2E of the Executor, we want to see if it integrates correctly.

@pytest.mark.asyncio
async def test_flow4_happy_path_dynamic_variables():
    """
    Flow 4 Scenario A: Happy Path
    Step 1: POST /login -> Extract token
    Step 2: GET /user/info with ${token} -> Verify replacement
    """
    
    # 1. Define Routes & Mock Responses
    with respx.mock(base_url="https://api.example.com") as respx_mock:
        # Route 1: Login
        login_route = respx_mock.post("/login").mock(
            return_value=Response(200, json={"data": {"token": "secret_abc_123"}, "status": "ok"})
        )
        
        # Route 2: User Info (Verify token in header)
        # We can use a side_effect to assert the header value dynamically, 
        # or just match it if respx supports header matching (it does, but let's be flexible)
        user_info_route = respx_mock.get("/user/info").mock(
            return_value=Response(200, json={"id": 1, "username": "test_user"})
        )
        
        # 2. Initialize Executor
        executor = APIExecutor(default_headers={"X-Test": "True"})
        async with executor:
            
            # --- Step 1: Login & Extract ---
            step1_ir = APIIR(
                method="POST",
                url="https://api.example.com/login",
                headers={"Content-Type": "application/json"},
                query_params={},
                body={"username": "user", "password": "pw"},
                assertions=[{"type": "status_code", "expected": 200}],
                extract={"token": "$.data.token"} # VariableExtractor supports $. syntax
            )
            
            result1 = await executor.execute(step1_ir)
            
            assert result1.success
            assert result1.extracted_values["token"] == "secret_abc_123"
            assert executor.get_context("token") == "secret_abc_123"
            
            # --- Step 2: Use Token ---
            step2_ir = APIIR(
                method="GET",
                url="https://api.example.com/user/info",
                headers={"Authorization": "Bearer ${token}"}, # Dynamic Variable
                query_params={},
                body=None,
                assertions=[
                    {"type": "status_code", "expected": 200},
                    {"type": "equals", "path": "$.username", "expected": "test_user"}
                ],
                extract={}
            )
            
            result2 = await executor.execute(step2_ir)
            
            assert result2.success
            assert result2.assertions_passed is not None
            
            # 3. Verify Mock Interaction (Deep Verification)
            # Check if Step 2 request header had the actual token
            assert user_info_route.called
            last_request = user_info_route.calls.last.request
            assert last_request.headers["Authorization"] == "Bearer secret_abc_123"


@pytest.mark.asyncio
async def test_flow4_error_path_assertion_failure():
    """
    Flow 4 Scenario B: Error Path (Assertion Failure)
    The API returns 200 OK, but the body doesn't match the assertion.
    Expect: success=False in result.
    """
    
    with respx.mock(base_url="https://api.example.com") as respx_mock:
        # Route: Returns 200 but wrong status in body
        respx_mock.get("/data").mock(
            return_value=Response(200, json={"status": "error", "message": "Something failed"})
        )
        
        executor = APIExecutor()
        async with executor:
            step_ir = APIIR(
                method="GET",
                url="https://api.example.com/data",
                headers={},
                query_params={},
                body=None,
                assertions=[
                    {"type": "status_code", "expected": 200}, # Should pass
                    {"type": "equals", "path": "$.status", "expected": "success"} # Should fail
                ],
                extract={}
            )
            
            result = await executor.execute(step_ir)
            
            # 4. Verify Failure
            assert not result.success
            # Check assertion details if available in ExecutionResult
            # We assume assertions_failed is a list of failed checks
            assert len(result.assertions_failed) > 0
            # Ideally verify message, but length check is robust enough for now
