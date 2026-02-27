import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.smart_ops.diagnostic_room import run_diagnostic_chat

# Since testing real LLM endpoints in unit tests is slow and brittle,
# we need to verify the parsing logic and the agent orchestration.
# AutoGen makes mocking tricky, but we can mock the `a_initiate_chat` 
# or just test the end-to-end flow with a mocked OpenAI response.

# For this test, we'll patch the groupchat message history to simulate 
# a successful diagnostic round.

@pytest.fixture
def mock_group_chat_messages():
    return [
        {"name": "Coordinator", "content": "Please analyze this error: Timeout Exception", "role": "user"},
        {"name": "Frontend_Expert", "content": "This looks like a Playwright timeout waiting for an element.", "role": "assistant"},
        {"name": "Backend_Expert", "content": "I don't see any server 500s or JVM heap logic errors here.", "role": "assistant"},
        {"name": "DBA_Expert", "content": "No SQL syntax errors or deadlocks observed.", "role": "assistant"},
        {"name": "Chief_Diagnostician", "content": '{"root_cause": "前端页面加载超时", "suggested_fix": "增加显式等待时间"} TERMINATE', "role": "assistant"}
    ]

@pytest.mark.asyncio
async def test_diagnostic_chat_parsing(monkeypatch, mock_group_chat_messages):
    error_msg = "TimeoutError: element #submit-btn not found within 3000ms"
    
    # We patch the UserProxyAgent's a_initiate_chat to just populate the messages
    # as if the group chat completed successfully.
    import app.services.smart_ops.diagnostic_room as d_room
    
    async def mock_initiate(*args, **kwargs):
        # The groupchat object is inside the manager, which we can't easily extract here without deeper patching,
        # but the function just inspects `group_chat.messages`. Let's mock the whole `GroupChat` class locally.
        pass 
        
    class MockGroupChat:
        def __init__(self, *args, **kwargs):
            self.messages = mock_group_chat_messages
            
    monkeypatch.setattr(d_room, "GroupChat", MockGroupChat)
    
    # We also need to bypass the actual LLM call. The easiest way for this specific test
    # is to mock the internal `user_proxy.a_initiate_chat` to do nothing, since MockGroupChat
    # will provide the messages.
    monkeypatch.setattr(d_room.UserProxyAgent, "a_initiate_chat", mock_initiate)
    # Also handle sync fallback
    monkeypatch.setattr(d_room.UserProxyAgent, "initiate_chat", MagicMock())
    
    # Run the function
    result = await d_room.run_diagnostic_chat(error_msg=error_msg, context="DOM: <body></body>")
    
    # Assert
    assert '{"root_cause": "前端页面加载超时", "suggested_fix": "增加显式等待时间"}' in result
    assert "TERMINATE" not in result # Ensure cleanup logic worked

@pytest.mark.asyncio
async def test_defect_manager_parsing(monkeypatch):
    """Test DefectManager properly parses the JSON returned from the chat"""
    from app.services.smart_ops.defect_manager import DefectManager
    
    manager = DefectManager()
    
    async def mock_run_chat(error_msg, context):
        return '```json\n{"root_cause": "模拟原因", "suggested_fix": "模拟修复"}\n```'
        
    import app.services.smart_ops.defect_manager as dm
    monkeypatch.setattr(dm, "run_diagnostic_chat", mock_run_chat)
    
    result = await manager.analyze_root_cause("fake error")
    
    assert result["root_cause"] == "模拟原因"
    assert result["suggested_fix"] == "模拟修复"
    
@pytest.mark.asyncio
async def test_defect_manager_bad_json(monkeypatch):
    """Test DefectManager handles bad JSON strings gracefully"""
    from app.services.smart_ops.defect_manager import DefectManager
    
    manager = DefectManager()
    
    async def mock_run_chat(error_msg, context):
        return 'This is not JSON at all. TERMINATE'
        
    import app.services.smart_ops.defect_manager as dm
    monkeypatch.setattr(dm, "run_diagnostic_chat", mock_run_chat)
    
    result = await manager.analyze_root_cause("fake error")
    
    assert "解析失败" in result["root_cause"]
    assert "This is not JSON" in result["suggested_fix"]
