import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import RefinedTestCase, RefinedTestStep
from app.core.ai_client import AIClientManager, Message

# --- Mock Data Structures ---

# Mock Document for Retrieval
class MockDocument:
    def __init__(self, content: str, metadata: Dict = None):
        self.content = content
        self.metadata = metadata or {}
        # Simulate attribute access for specific fields if needed
        self.method = self.metadata.get("method", "GET")
        self.path = self.metadata.get("path", "/api/test")

# Mock AI Response
class MockAIResponse:
    def __init__(self, content: str):
        self.content = content

# Sample LLM Output (Draft JSON)
VALID_DRAFT_JSON = """
{
    "case_name": "Login and Checkout",
    "description": "User logs in and checks out cart",
    "steps": [
        {
            "step_id": "step_1",
            "intent": "Login",
            "method": "POST",
            "url_path": "/api/login",
            "description": "User authentication",
            "input_data": {"user": "test", "pass": "123"},
            "expected_outcome": "token_123"
        },
        {
            "step_id": "step_2",
            "intent": "Checkout",
            "method": "POST",
            "url_path": "/api/checkout",
            "description": "Process payment",
            "input_data": {"cart_id": "c1"},
            "expected_outcome": "success"
        }
    ]
}
"""

@pytest.fixture
def mock_design_deps():
    """
    Setup mocks for DesignService dependencies
    """
    with patch("app.services.neural_design.service.RagRetriever") as mock_rag_cls, \
         patch("app.services.neural_design.service.KnowledgeRetriever") as mock_know_cls, \
         patch("app.services.neural_design.service.get_ai_manager") as mock_ai_getter, \
         patch("app.services.neural_design.service.repair_json") as mock_repair:
        
        # Mock repair_json to just load JSON
        import json
        def simple_repair(text):
            return json.loads(text)
        mock_repair.side_effect = simple_repair

        # 1. Mock RagRetriever
        mock_retriever = mock_rag_cls.return_value
        async def default_retrieve(*args, **kwargs):
            return []
        mock_retriever.retrieve = MagicMock(side_effect=default_retrieve)
        
        # 2. Mock KnowledgeRetriever
        mock_knowledge = mock_know_cls.return_value
        mock_knowledge.retrieve = MagicMock(side_effect=default_retrieve)
        
        # 3. Mock AIClientManager
        mock_ai = MagicMock(spec=AIClientManager)
        async def default_invoke(*args, **kwargs):
            return MockAIResponse(content="{}")
        mock_ai.invoke = MagicMock(side_effect=default_invoke)
        
        # Mock the getter to return our mock_ai
        mock_ai_getter.return_value = mock_ai
        
        yield {
            "retriever": mock_retriever,
            "knowledge": mock_knowledge,
            "ai": mock_ai
        }

@pytest.mark.asyncio
async def test_flow1_happy_path(mock_design_deps):
    """
    Flow 1: Neural Design - Happy Path
    
    Scenario: User inputs "Login and Checkout".
    1. RAG Retrieve: Returns API definitions (POST /login, POST /checkout).
    2. Knowledge Retrieve: Returns business rules (Auth required).
    3. AI Generate: Returns valid Draft JSON.
    4. AI Critic: Returns valid Refined JSON (or confirms draft).
    5. Service: Converts to RefinedTestCase.
    """
    mock_retriever = mock_design_deps["retriever"]
    mock_knowledge = mock_design_deps["knowledge"]
    mock_ai = mock_design_deps["ai"]
    
    # --- Setup Mocks ---
    
    # 1. Mock RAG Retrieval (API Definitions)
    async def mock_rag_retrieve(query, project_id):
        return [
            MockDocument("POST /login", {"method": "POST", "path": "/api/login", "summary": "User Login"}),
            MockDocument("POST /checkout", {"method": "POST", "path": "/api/checkout", "summary": "Cart Checkout"})
        ]
    mock_retriever.retrieve.side_effect = mock_rag_retrieve
    
    # 2. Mock Knowledge Retrieval
    async def mock_know_retrieve(query, project_id):
        return [MockDocument("Rule: Checkout requires active session")]
    mock_knowledge.retrieve.side_effect = mock_know_retrieve
    
    # Mock AI Generation
    # Order of calls: 
    # Mock AI Generation
    # Order of calls: 
    #   1. Neural Intent Parser (Draft Generation) -> Returns VALID_DRAFT_JSON
    #   2. Critic (Self-Correction) -> Returns VALID_DRAFT_JSON (Verification passthrough)
    async def mock_ai_invoke(*args, **kwargs):
        # We can inspect messages to decide what to return, or just return sequence
        return MockAIResponse(content=VALID_DRAFT_JSON)
        
    mock_ai.invoke.side_effect = mock_ai_invoke

    # --- Execute SUT ---
    service = DesignService(ai_manager=mock_ai, retriever=mock_retriever, knowledge_retriever=mock_knowledge)
    
    scenario = {
        "name": "Login and Checkout",
        "description": "User logs in and checks out cart",
        "test_points": ["Login success", "Checkout success"]
    }
    
    result = await service.generate_test_case(scenario, project_id="proj_123")
    
    # --- Assertions ---
    
    # 1. Verify RAG Retrieval called correctly
    expected_query = "User logs in and checks out cart Login success Checkout success"
    mock_retriever.retrieve.assert_called_once_with(expected_query, "proj_123")
    
    # 2. Verify Knowledge Retrieval called
    mock_knowledge.retrieve.assert_called_once_with(expected_query, "proj_123")
    
    # 3. Verify AI Invocation
    assert mock_ai.invoke.call_count >= 1
    
    # Check Context injection in 1st call (Draft)
    # Note: invoke is called positionally: invoke(module, messages)
    draft_call_args = mock_ai.invoke.call_args_list[0]
    messages = draft_call_args.args[1] # messages is 2nd arg
    user_msg = messages[-1].content
    assert "POST /api/login" in user_msg, "API Context missing in prompt"
    assert "Rule: Checkout requires active session" in user_msg, "Knowledge Context missing in prompt"
    
    # 4. Verify Result Structure
    assert isinstance(result, RefinedTestCase)
    
@pytest.mark.asyncio
async def test_flow1_rag_miss_fallback(mock_design_deps):
    """
    Flow 1 Error Path: RAG Miss
    """
    mock_retriever = mock_design_deps["retriever"]
    mock_knowledge = mock_design_deps["knowledge"] # Need this to avoid None error if service calls it
    mock_ai = mock_design_deps["ai"]
    
    # --- Setup Mocks ---
    
    # 1. Mock RAG Retrieval (Empty)
    async def mock_rag_empty(*args, **kwargs):
        return []
    mock_retriever.retrieve.side_effect = mock_rag_empty
    
    # 2. Mock Knowledge Retrieval (Empty) -> Fix for AttributeError 'NoneType' has no attribute 'get' if logic iterates
    async def mock_know_empty(*args, **kwargs):
        return []
    mock_knowledge.retrieve.side_effect = mock_know_empty
    
    # 3. Mock AI Generation
    async def mock_ai_invoke(*args, **kwargs):
        return MockAIResponse(content=VALID_DRAFT_JSON)
    mock_ai.invoke.side_effect = mock_ai_invoke
    
    # --- Execute SUT ---
    service = DesignService(ai_manager=mock_ai, retriever=mock_retriever, knowledge_retriever=mock_knowledge)
    
    scenario = {"name": "Generic Case", "description": "Do something"}
    
    result = await service.generate_test_case(scenario, project_id="proj_123")
    
    # --- Assertions ---
    
    # 1. Verify Result created
    assert isinstance(result, RefinedTestCase)
    
    # 2. Verify Prompt Content contains Fallback Message
    draft_call_args = mock_ai.invoke.call_args_list[0]
    # Check args position for messages
    messages = draft_call_args.args[1]
    user_msg = messages[-1].content
    
    assert "未检索到具体 API 定义" in user_msg
