import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.engines.dispatcher import Dispatcher
from app.engines.left_pupil import APIExecutor
from app.schemas.execution import ExecutionMode, TCIR

@pytest.mark.asyncio
async def test_context_injection_flow():
    """
    Integration test for Context Injection (Extraction -> Injection)
    
    Scenario:
    1. Step 1: Login (returns token) -> Extract token
    2. Step 2: Get Profile (uses token) -> Verify token injection
    """
    
    # 1. Setup Engine & Dispatcher
    dispatcher = Dispatcher()
    api_executor = APIExecutor()
    
    # Mock HTTP Client in Executor to avoid real network calls
    mock_client = AsyncMock()
    api_executor._client = mock_client
    
    dispatcher.attach_engines(left_pupil=api_executor)
    
    # 2. Define Test Case (TC-IR)
    tc_ir = TCIR(
        id="TC-CONTEXT-001",
        name="Context Injection Test",
        mode=ExecutionMode.API,
        steps=[
            # Step 1: Login & Extract
            {
                "step_id": "step1",
                "name": "Login",
                "step_type": "API",
                "method": "POST",
                "url": "https://api.example.com/login",
                "body": {"username": "user", "password": "pwm"},
                "extract": {
                    "auth_token": "data.token",
                    "user_id": "data.user.id"
                },
                "expected_status_code": 200
            },
            # Step 2: Use Token
            {
                "step_id": "step2",
                "name": "Get Profile",
                "step_type": "API",
                "method": "GET",
                # Logically we want to test URL replacement too?
                "url": "https://api.example.com/users/${user_id}", 
                "headers": {
                    "Authorization": "Bearer ${auth_token}",
                    "X-User-ID": "${user_id}"
                },
                "expected_status_code": 200
            }
        ]
    )
    
    # 3. Setup Mocks for Step 1 & Step 2
    
    # Response for Step 1
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {
        "data": {
            "token": "mock-token-12345",
            "user": {"id": "user-999"}
        }
    }
    resp1.headers = {}
    
    # Response for Step 2
    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {"msg": "success"}
    resp2.headers = {}
    
    # Configure mock_client.request side_effect
    mock_client.request.side_effect = [resp1, resp2]
    
    # 4. Execute
    result = await dispatcher.execute(tc_ir)
    
    # 5. Verify
    assert result.success is True
    assert len(result.step_results) == 2
    assert result.step_results[0].success is True
    assert result.step_results[1].success is True
    
    # Check calls to verify injection
    assert mock_client.request.call_count == 2
    
    # Verify Step 2 Request (Injection)
    call_args_list = mock_client.request.call_args_list
    step2_call = call_args_list[1]
    
    # args: method, url, ... kwargs: headers, ...
    # APIExecutor calls: client.request(method=..., url=..., headers=...)
    kw = step2_call.kwargs
    
    # Verify URL replacement
    assert kw["url"] == "https://api.example.com/users/user-999"
    
    # Verify Header replacement
    headers = kw["headers"]
    assert headers["Authorization"] == "Bearer mock-token-12345"
    assert headers["X-User-ID"] == "user-999"
    
    print("✅ Context Injection Verified!")

if __name__ == "__main__":
    asyncio.run(test_context_injection_flow())
