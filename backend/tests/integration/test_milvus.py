
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.smart_ops.defect_manager import DefectManager
from app.services.smart_ops.vector_store import VectorStore

class MockCollection:
    def __init__(self, name):
        self.name = name
    def load(self): pass
    def create_index(self, field_name, index_params): pass
    def insert(self, data): pass
    def flush(self): pass
    def search(self, data, anns_field, param, limit, output_fields):
        # Return mock hits
        # Structure: [[Hit(score, entity)]]
        mock_hit = MagicMock()
        mock_hit.score = 0.95
        mock_hit.entity.get.side_effect = lambda k: {
            "error_msg": "Test Error",
            "root_cause": "Test Cause",
            "solution": "Test Solution"
        }.get(k)
        return [[mock_hit]]

@pytest.fixture
def mock_milvus():
    with patch("app.services.smart_ops.vector_store.connections"), \
         patch("app.services.smart_ops.vector_store.utility"), \
         patch("app.services.smart_ops.vector_store.Collection", side_effect=MockCollection):
        yield

@pytest.fixture
def mock_embeddings():
    with patch("app.services.smart_ops.defect_manager.OpenAIEmbeddings") as MockEmbed:
        instance = MockEmbed.return_value
        # Mock async embedding
        instance.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        yield instance

@pytest.mark.asyncio
async def test_defect_manager_flow(mock_milvus, mock_embeddings):
    manager = DefectManager()
    
    # 1. Connect
    await manager.connect()
    assert manager.vector_store._connected is True
    
    # 2. Store Defect
    await manager.store_defect(
        error_msg="NullPointerException in login",
        root_cause="User object is null",
        solution="Check user existence"
    )
    
    # Verify embedding called
    mock_embeddings.aembed_query.assert_called()
    
    # 3. Search Defect
    results = await manager.find_similar_defect("Login failed with null pointer")
    
    assert len(results) == 1
    assert results[0]["error_msg"] == "Test Error"
    assert results[0]["score"] == 0.95
