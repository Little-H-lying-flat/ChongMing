
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.left_pupil.knowledge_ingestor import KnowledgeIngestor
from app.services.left_pupil.knowledge_retriever import KnowledgeRetriever
from app.services.neural_design.service import DesignService

@pytest.mark.asyncio
async def test_knowledge_ingestion_and_retrieval():
    """
    Verify Knowledge Ingestion and Retrieval Flow with Mocks
    (We don't test actual ChromaDB interaction here to stay fast/isolated)
    """
    # 1. Setup Mocks
    mock_chroma = MagicMock()
    ingestor = KnowledgeIngestor(chroma_client=mock_chroma)
    retriever = KnowledgeRetriever(chroma_client=mock_chroma)
    
    # Mock Embeddings (Return dummy vector)
    with patch.object(ingestor, '_get_embeddings', return_value=[[0.1]*1536]):
        # 2. Test Ingestion
        markdown_content = """# Business Rules
## Order Limits
Orders count strictly greater than 1000 must be approved.

## Token Expiry
Tokens expire after 30 minutes.
"""
        count = ingestor.ingest_text(markdown_content, "rules.md", "proj_test")
        
        # Verify chunking (should be 2 chunks: Order Limits, Token Expiry)
        # However, our simple chunker splits by header.
        # Header "Business Rules" -> empty content? or contains subheaders?
        # Let's check implementation behavior: splits by lines startswith #.
        # "Order Limits" chunk, "Token Expiry" chunk.
        assert count > 0
        mock_chroma.add_documents.assert_called_once()
        
    # 3. Test Retrieval
    # Mock Chroma Query Result
    mock_chroma.query.return_value = {
        "ids": [["chunk1"]],
        "documents": [["Orders count strictly greater than 1000 must be approved."]],
        "metadatas": [[{"header": "Order Limits"}]],
        "distances": [[0.1]]
    }
    
    # Patch async _get_embeddings on retriever
    # We use AsyncMock for the patch
    with patch.object(retriever, '_get_embeddings', new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [[0.1]*1536]
        
        results = await retriever.retrieve("order limit", "proj_test")
        
        assert len(results) == 1
        assert "1000" in results[0].content
        assert results[0].metadata["header"] == "Order Limits"

@pytest.mark.asyncio
async def test_neural_design_integration():
    """
    Verify NeuralDesignService uses KnowledgeRetriever
    """
    # 1. Setup
    mock_ai = AsyncMock()
    mock_rag = MagicMock()
    mock_knowledge = AsyncMock()
    
    service = DesignService(
        ai_manager=mock_ai, 
        retriever=mock_rag,
        knowledge_retriever=mock_knowledge
    )
    
    # Mock Knowledge Return
    mock_knowledge.retrieve.return_value = [
        MagicMock(content="Rule: User must be 18+")
    ]
    
    # Mock RAG Return (API)
    mock_rag.retrieve.return_value = [] 
    
    # Mock AI Response for Draft Generation
    mock_ai.invoke.return_value = MagicMock(content="""
    {
        "case_name": "Test Case",
        "steps": [{"intent": "step1"}]
    }
    """)
    
    # PATCH: Override retrieve method to be async compatible if it's not already handled by AsyncMock auto-magic
    # Since we passed mock_knowledge as AsyncMock, its methods are AsyncMock.
    # But if we set return_value to strict list, it might complain if called with await.
    # Actually AsyncMock calling returns a coroutine that resolves to return_value.
    # The error "object list can't be used in 'await' expression" suggests it wasn't treated as coroutine.
    # Let's ensure it is.
    
    # Re-setup mocks more explicitly using object patching (both are @property with no setter)
    mock_kr = AsyncMock()
    mock_kr.retrieve.return_value = [
        MagicMock(content="Rule: User must be 18+")
    ]
    mock_retriever = AsyncMock()
    mock_retriever.retrieve.return_value = []
    with patch.object(type(service), 'knowledge_retriever', new_callable=lambda: property(lambda self: mock_kr)), \
         patch.object(type(service), 'retriever', new_callable=lambda: property(lambda self: mock_retriever)):
    
        # 2. Execute
        scenario = {"name": "Test Scenario", "description": "Verify Age Check"}
        await service.generate_test_case(scenario, "proj_test")
    
        # 3. Verify interaction
        # Confirm Knowledge Retriever was called
        mock_kr.retrieve.assert_called_once()
    
        # Confirm Prompt contained the knowledge
        call_args = mock_ai.invoke.call_args_list[0]
        # Check messages content
        # messages is named arg? or positional? Check service implementation.
        # invoke(module, messages) -> args[0]=module, args[1]=messages
        messages = call_args[0][1] # messages list
        user_msg = messages[1].content
        assert "Rule: User must be 18+" in user_msg
        assert "领域知识/业务规则" in user_msg
