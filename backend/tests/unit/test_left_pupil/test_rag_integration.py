import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.left_pupil.spec_ingestor import SpecIngestor
from app.services.left_pupil.rag_retriever import RagRetriever

@pytest.fixture
def test_project_id():
    return "test_proj_integration"

@pytest.fixture
def ingestor():
    return SpecIngestor()

@pytest.fixture
def retriever(ingestor):
    r = RagRetriever(ingestor=ingestor)
    # Mock LLM expansion to return just a simple expansion
    r._expand_intent = AsyncMock(return_value=["users", "get users"])
    return r

@pytest.mark.asyncio
async def test_full_rag_flow(ingestor, retriever, test_project_id):
    # 1. Ingest
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "operationId": "getUsers",
                    "summary": "Get all users list",
                    "responses": {"200": {"description": "OK"}}
                }
            },
            "/orders": {
                "post": {
                    "operationId": "createOrder",
                    "summary": "Create new order",
                    "responses": {"201": {"description": "Created"}}
                }
            }
        }
    }
    
    # Clean up before test
    ingestor.delete_project(test_project_id)
    
    try:
        count = ingestor.ingest_spec(spec, test_project_id)
        assert count == 2
        
        # 2. Verify Chroma
        total = ingestor.count(test_project_id)
        assert total == 2
        
        # 3. Retrieve
        # We mocked expansion so it won't call LLM
        results = await retriever.retrieve("I want to find users", test_project_id)
        
        assert len(results) > 0
        assert results[0].path == "/users"
        assert results[0].method == "GET"
        print(f"Retrieved: {results[0].method} {results[0].path}")
        
    finally:
        # Clean up
        ingestor.delete_project(test_project_id)
