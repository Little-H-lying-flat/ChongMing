
from typing import List, Dict, Any, Optional
from loguru import logger
from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
)
from app.core.config import settings

class VectorStore:
    """
    Milvus Vector Store Wrapper
    
    负责 Milvus 连接管理、集合创建、数据插入和向量搜索。
    """
    
    def __init__(self, collection_name: str = "defect_knowledge_base", dim: int = 1536):
        self.collection_name = collection_name
        self.dim = dim
        self.collection: Optional[Collection] = None
        self._connected = False

    def connect(self):
        """连接到 Milvus"""
        if self._connected:
            return

        try:
            # Parse host/port from config? Or use default
            # settings.MILVUS_HOST, settings.MILVUS_PORT
            host = getattr(settings, "MILVUS_HOST", "localhost")
            port = getattr(settings, "MILVUS_PORT", "19530")
            
            logger.info(f"Connecting to Milvus at {host}:{port}...")
            connections.connect("default", host=host, port=port)
            self._connected = True
            self._init_collection()
            logger.info("Connected to Milvus successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            # Don't raise, allow app to run without Milvus (soft failure)

    def _init_collection(self):
        """初始化集合 (如果不存在则创建)"""
        if not self._connected:
            return

        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            self.collection.load()
            return

        logger.info(f"Creating collection: {self.collection_name}")
        
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            FieldSchema(name="error_msg", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="root_cause", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="solution", dtype=DataType.VARCHAR, max_length=65535),
            # Metadata as JSON string if needed, or separate fields
        ]
        
        schema = CollectionSchema(fields, "Defect Knowledge Base")
        self.collection = Collection(self.collection_name, schema)
        
        # Create Index for faster search
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        self.collection.load()

    def insert(self, embedding: List[float], metadata: Dict[str, Any]):
        """插入向量"""
        if not self.collection:
            return
            
        data = [
            [embedding], # vectors
            [metadata.get("error_msg", "")],
            [metadata.get("root_cause", "")],
            [metadata.get("solution", "")],
        ]
        
        self.collection.insert(data)
        self.collection.flush() # Ensure visible
        logger.info("Inserted defect into Vector Store.")

    def search(self, query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        if not self.collection:
            return []
            
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10},
        }
        
        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["error_msg", "root_cause", "solution"]
        )
        
        hits = []
        for hits_i in results:
            for hit in hits_i:
                hits.append({
                    "score": hit.score,
                    "error_msg": hit.entity.get("error_msg"),
                    "root_cause": hit.entity.get("root_cause"),
                    "solution": hit.entity.get("solution")
                })
                
        return hits
