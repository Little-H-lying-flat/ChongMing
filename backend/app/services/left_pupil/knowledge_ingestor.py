"""
Knowledge Ingestor
Responsible for ingesting unstructured text/markdown into Vector DB for RAG.
"""

import hashlib
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.chroma_client import ChromaClient
import httpx
import logging

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeChunk:
    chunk_id: str
    content: str
    metadata: dict = field(default_factory=dict)

class KnowledgeIngestor:
    """
    Ingests Knowledge (Markdown/Text) into ChromaDB.
    Collection Prefix: project_knowledge_
    """
    
    COLLECTION_PREFIX = "project_knowledge_"
    
    def __init__(self, chroma_client: Optional[ChromaClient] = None):
        self.chroma = chroma_client or ChromaClient.get_instance()

    def _get_collection_name(self, project_id: str) -> str:
        return f"{self.COLLECTION_PREFIX}{project_id}"

    def ingest_file(self, file_path: str, project_id: str) -> int:
        """Ingest a file (currently supports .md, .txt)"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return self.ingest_text(content, file_path, project_id)
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            return 0

    def ingest_text(self, content: str, source_name: str, project_id: str) -> int:
        """Ingest raw text string"""
        chunks = self._chunk_text(content, source_name)
        return self._ingest_chunks(chunks, project_id)

    def _ingest_chunks(self, chunks: List[KnowledgeChunk], project_id: str) -> int:
        if not chunks:
            return 0
            
        collection_name = self._get_collection_name(project_id)
        
        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        
        embeddings = self._get_embeddings(documents)
        
        self.chroma.add_documents(
            collection_name=collection_name,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )
        
        logger.info(f"Ingested {len(chunks)} knowledge chunks for project {project_id}")
        return len(chunks)

    def _chunk_text(self, text: str, source: str) -> List[KnowledgeChunk]:
        """
        Simple Markdown Recursive Chunking strategy.
        Splits by Headers (#, ##, ###) or newlines if too long.
        """
        # 1. Split by H2/H3 headers for logical grouping
        # Regex to find headers: ^#{1,3}\s+(.*)
        # This is a basic implementation. For production, use langchain's RecursiveCharacterTextSplitter.
        
        lines = text.split('\n')
        chunks = []
        current_chunk_lines = []
        current_header = "General"
        
        for line in lines:
            if line.strip().startswith('#'):
                # Save previous chunk
                if current_chunk_lines:
                    self._add_chunk(chunks, current_chunk_lines, current_header, source)
                    current_chunk_lines = []
                
                current_header = line.strip().lstrip('#').strip()
                current_chunk_lines.append(line)
            else:
                current_chunk_lines.append(line)
        
        # Add last chunk
        if current_chunk_lines:
             self._add_chunk(chunks, current_chunk_lines, current_header, source)
             
        return chunks

    def _add_chunk(self, chunks: List, lines: List[str], header: str, source: str):
        content = "\n".join(lines).strip()
        if not content:
            return
            
        # If content is too large (> 1000 chars), split further? 
        # For now, keep it simple.
        
        chunk_id = hashlib.md5(content.encode()).hexdigest()[:12]
        chunks.append(KnowledgeChunk(
            chunk_id=chunk_id,
            content=content,
            metadata={
                "source": source,
                "header": header,
                "type": "markdown"
            }
        ))

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings using the configured AI provider.
        (Duplicated from SpecIngestor for isolation)
        """
        if not texts:
            return []
            
        embeddings = []
        batch_size = 10
        
        headers = {
            "Authorization": f"Bearer {settings.QWEN_API_KEY}",
            "Content-Type": "application/json"
        }
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            payload = {
                "model": settings.MODEL_EMBEDDING,
                "input": batch
            }
            
            try:
                url = f"{settings.QWEN_BASE_URL}/embeddings"
                resp = httpx.post(url, headers=headers, json=payload, timeout=30.0)
                
                if resp.status_code == 200:
                    data = resp.json()
                    batch_embeddings = [item["embedding"] for item in data.get("data", [])]
                    embeddings.extend(batch_embeddings)
                else:
                    logger.error(f"Embedding API failed: {resp.text}")
                    embeddings.extend([[] for _ in batch])
            except Exception as e:
                 logger.error(f"Embedding request failed: {e}")
                 embeddings.extend([[] for _ in batch])
                 
        return embeddings

    def delete_knowledge(self, project_id: str) -> bool:
        return self.chroma.delete_collection(self._get_collection_name(project_id))
