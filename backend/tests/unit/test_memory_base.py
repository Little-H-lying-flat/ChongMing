import pytest
import os
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Ensure tests use sqlite and memory brokers
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.core.memory_base import MemoryBase

@pytest.fixture
def mock_mem0():
    with patch("app.core.memory_base.Memory", autospec=True) as mock_memory_cls:
        # Mock instance returned by Memory.from_config
        mock_instance = MagicMock()
        mock_memory_cls.from_config.return_value = mock_instance
        yield mock_instance

def test_memory_base_init(mock_mem0):
    # Testing Singleton pattern and init
    MemoryBase._instance = None
    mem_base = MemoryBase()
    assert mem_base.memory is not None
    assert mem_base is MemoryBase() # Singleton check

def test_add_memory(mock_mem0):
    MemoryBase._instance = None
    mem_base = MemoryBase()
    
    mock_mem0.add.return_value = {"id": "mem_123"}
    
    res = mem_base.add_memory("A cool testing preference", "user_1", "proj_2")
    
    assert res == {"id": "mem_123"}
    mock_mem0.add.assert_called_once_with(
        messages=[{"role": "user", "content": "A cool testing preference"}],
        user_id="user_1",
        session_id=None,
        metadata={"project_id": "proj_2"}
    )

def test_search_memory(mock_mem0):
    MemoryBase._instance = None
    mem_base = MemoryBase()
    
    # Mocking search response
    mock_mem0.search.return_value = [
        {"memory": "Preference 1", "score": 0.9},
        {"memory": "Preference 2", "score": 0.8}
    ]
    
    res = mem_base.search_memory("testing", "user_1", "proj_2")
    
    assert "Preference 1" in res
    assert "Preference 2" in res
    assert "历史经验与偏好参考" in res
    
    mock_mem0.search.assert_called_once_with(
        query="testing",
        user_id="user_1",
        limit=5,
        filters={"project_id": "proj_2"}
    )
