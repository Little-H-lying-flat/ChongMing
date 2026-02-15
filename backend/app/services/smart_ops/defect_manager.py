
from typing import List, Dict, Optional
from loguru import logger
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
from app.services.smart_ops.vector_store import VectorStore

class DefectManager:
    """
    缺陷分析管理器 (Defect Manager)
    
    Integrates AI (Embeddings) with Vector DB (Milvus) 
    to enable semantic search for similar defects.
    """
    
    def __init__(self):
        self.vector_store = VectorStore()
        
        # Initialize Embeddings
        # Uses OpenAI compatible API (e.g. Qwen via DashScope if compatible, or actual OpenAI)
        # Note: Qwen standard API might need custom wrapper if not fully OpenAI-compatible for embeddings.
        # For now, assuming standard OpenAI interface or mock for local dev.
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.QWEN_API_KEY, 
            openai_api_base=settings.QWEN_BASE_URL,
            model=settings.MODEL_EMBEDDING
        )
        
    async def connect(self):
        """Connect to underlying storage"""
        self.vector_store.connect()

    async def store_defect(self, error_msg: str, root_cause: str, solution: str):
        """
        Store a new defect analysis
        1. Convert error_msg -> Embedding
        2. Store in Milvus
        """
        try:
            # Generate Embedding
            # Combine text for richer context? Or just error message?
            text_to_embed = f"{error_msg}\nRoot Cause: {root_cause}"
            vector = await self.embeddings.aembed_query(text_to_embed)
            
            # Store
            self.vector_store.insert(
                embedding=vector,
                metadata={
                    "error_msg": error_msg,
                    "root_cause": root_cause,
                    "solution": solution
                }
            )
            logger.info("Defect stored successfully.")
        except Exception as e:
            logger.error(f"Failed to store defect: {e}")

    async def find_similar_defect(self, error_msg: str, top_k: int = 3) -> List[Dict]:
        """
        Find minimal defects
        """
        try:
            vector = await self.embeddings.aembed_query(error_msg)
            results = self.vector_store.search(vector, top_k=top_k)
            return results
        except Exception as e:
            logger.error(f"Failed to find similar defects: {e}")
            return []
