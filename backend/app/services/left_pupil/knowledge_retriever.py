"""
Knowledge Retriever
Retrieves relevant unstructured knowledge from ChromaDB.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from app.core.config import settings
from app.core.chroma_client import ChromaClient
import httpx
import logging

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeContext:
    chunk_id: str
    content: str
    metadata: dict
    relevance: float

class KnowledgeRetriever:
    """
    Retrieves knowledge context based on query/intent.
    Collection Prefix: project_knowledge_
    """
    
    COLLECTION_PREFIX = "project_knowledge_"
    
    def __init__(self, chroma_client: Optional[ChromaClient] = None):
        self.chroma = chroma_client or ChromaClient.get_instance()

    def _get_collection_name(self, project_id: str) -> str:
        return f"{self.COLLECTION_PREFIX}{project_id}"

    async def retrieve(self, query: str, project_id: str, top_k: int = 3) -> List[KnowledgeContext]:
        """
        Retrieve relevant knowledge chunks.
        """
        if not query:
            return []
            
        collection_name = self._get_collection_name(project_id)
        
        # 1. Generate Query Embeddings
        query_embedding = await self._get_embeddings([query])
        if not query_embedding or not query_embedding[0]:
            logger.warning("Failed to generate query embedding.")
            return []
            
        # 2. Query Chroma (Sync operation wrapped if needed, but here simple call)
        # Chroma client is sync. In async function, this blocks loop.
        # Ideally run_in_executor, but for prototype direct call is ok if fast.
        try:
            results = self.chroma.query(
                collection_name=collection_name,
                query_texts=[query],
                query_embeddings=query_embedding,
                n_results=top_k
            )
        except Exception as e:
            # Collection might not exist
            logger.debug(f"Knowledge Retrieval failed (likely no knowledge base): {e}")
            return []
            
        contexts = []
        if results and results.get("ids"):
            ids = results["ids"][0]
            documents = results["documents"][0] if results.get("documents") else []
            metadatas = results["metadatas"][0] if results.get("metadatas") else []
            distances = results["distances"][0] if results.get("distances") else []
            
            for i, chunk_id in enumerate(ids):
                score = 1.0 - distances[i] if i < len(distances) else 0.0
                
                contexts.append(KnowledgeContext(
                    chunk_id=chunk_id,
                    content=documents[i] if i < len(documents) else "",
                    metadata=metadatas[i] if i < len(metadatas) else {},
                    relevance=score
                ))
                
        return contexts

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings using the configured AI provider.
        """
        if not texts:
            return []
            
        embeddings = []
        batch_size = 10
        
        headers = {
            "Authorization": f"Bearer {settings.QWEN_API_KEY}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                payload = {
                    "model": settings.MODEL_EMBEDDING,
                    "input": batch
                }
                try:
                    url = f"{settings.QWEN_BASE_URL}/embeddings"
                    resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        batch_embeddings = [item["embedding"] for item in data.get("data", [])]
                        embeddings.extend(batch_embeddings)
                    else:
                        embeddings.extend([[] for _ in batch])
                except Exception as e:
                     embeddings.extend([[] for _ in batch])
                     
        return embeddings
