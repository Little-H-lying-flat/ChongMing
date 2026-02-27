"""
重明长程记忆基座 (Long-Term Memory Base)

封装 mem0ai 库，提供跨会话和跨项目的测试经验持久化功能。
"""

from mem0 import Memory
from app.core.config import settings
from app.core.logging import logger
from typing import List, Dict, Any, Optional

class MemoryBase:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryBase, cls).__new__(cls)
            cls._instance._init_memory()
        return cls._instance
        
    def _init_memory(self):
        is_test = "test" in str(settings.DATABASE_URL) or "memory" in str(settings.DATABASE_URL)
        db_path = "./mem0_qdrant_db_test" if is_test else "./mem0_qdrant_db"
        
        # Configure Mem0 to use Qwen compatible mode via OpenAI provider
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": settings.QWEN_API_KEY,
                    "model": settings.MODEL_GENERAL_CHAT,
                    "openai_base_url": settings.QWEN_BASE_URL
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "api_key": settings.QWEN_API_KEY,
                    "model": "text-embedding-v3",
                    "openai_base_url": settings.QWEN_BASE_URL
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "chongming_mem0",
                    "path": db_path
                }
            }
        }
        try:
            self.memory = Memory.from_config(config)
            logger.info("Mem0 MemoryBase initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")
            self.memory = None

    def add_memory(self, content: str, user_id: str, project_id: Optional[str] = None, session_id: Optional[str] = None):
        """Add memory specifically scoped to a user and project (tenant isolation)"""
        if not self.memory:
            return None
            
        metadata = {}
        if project_id:
            metadata["project_id"] = project_id
            
        try:
            res = self.memory.add(
                messages=[{"role": "user", "content": content}],
                user_id=user_id,
                metadata=metadata
            )
            logger.info(f"Memory added for user {user_id} (Project: {project_id}): {content[:50]}...")
            return res
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return None

    def search_memory(self, query: str, user_id: str, project_id: Optional[str] = None, limit: int = 5) -> str:
        """Search memory for a specific user and project. Returns a context string."""
        if not self.memory:
            return ""
            
        filters = {}
        if project_id:
            filters["project_id"] = project_id
            
        try:
            results = self.memory.search(
                query=query,
                user_id=user_id,
                limit=limit,
                filters=filters if filters else None
            )
            if not results:
                return ""
            
            # Combine retrieved memories
            memories = [r["memory"] for r in results if "memory" in r]
            combined = "\n- ".join(memories)
            if combined:
                return "【历史经验与偏好参考】\n- " + combined
            return ""
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return ""

# Export a global singleton instance
memory_base = MemoryBase()
