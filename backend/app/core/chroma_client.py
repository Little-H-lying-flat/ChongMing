"""
ChromaDB 向量数据库客户端 (HTTP 版)

由于 chromadb 官方库在 Python 3.14/Pydantic v2 环境下存在兼容性问题，
本客户端使用 httpx 直接对接 ChromaDB Docker 服务 REST API。
"""

import logging
import os
from typing import Optional, Any, List, Dict
import httpx

logger = logging.getLogger(__name__)

class ChromaClient:
    """
    ChromaDB HTTP 客户端
    
    直接通过 REST API 与 ChromaDB 服务交互
    默认地址: http://localhost:8001
    """
    
    _instance: Optional["ChromaClient"] = None
    
    
    def __init__(self, host: str = "localhost", port: int = 8001):
        """
        初始化 ChromaDB 客户端
        """
        self.host = os.getenv("CHROMADB_HOST", host)
        self.port = int(os.getenv("CHROMADB_PORT", port))
        self.tenant = "default_tenant"
        self.database = "default_database"
        self.base_url = f"http://{self.host}:{self.port}/api/v1" # Keep generic base, but methods use v2 paths
        # Actually better to set base_url to root and append full path
        self.base_url = f"http://{self.host}:{self.port}"
        self.client = httpx.Client(base_url=self.base_url, timeout=10.0)
        
    @classmethod
    def get_instance(cls) -> "ChromaClient":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def heartbeat(self) -> bool:
        """检查服务连通性"""
        try:
            resp = self.client.get("/api/v2/heartbeat")
            return resp.status_code == 200
        except Exception:
            return False

    def _get_base_path(self) -> str:
        return f"/api/v2/tenants/{self.tenant}/databases/{self.database}"

    def _get_collection_id(self, name: str) -> Optional[str]:
        """获取集合 ID"""
        try:
            resp = self.client.get(f"{self._get_base_path()}/collections/{name}")
            if resp.status_code == 200:
                return resp.json()["id"]
        except Exception:
            pass
        return None

    def get_collection(self, name: str) -> Dict[str, Any]:
        """
        获取或创建集合
        返回集合信息的字典
        """
        try:
            # Try to get existing
            resp = self.client.get(f"{self._get_base_path()}/collections/{name}")
            if resp.status_code == 200:
                return resp.json()
            
            # Create if not exists
            resp = self.client.post(f"{self._get_base_path()}/collections", json={
                "name": name, 
                "get_or_create": True,
                "metadata": {"hnsw:space": "cosine"}
            })
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to get/create collection {name}: {e}")
            return {}

    def delete_collection(self, name: str) -> bool:
        """删除集合"""
        try:
            resp = self.client.delete(f"{self._get_base_path()}/collections/{name}")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False
            
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        try:
            resp = self.client.get(f"{self._get_base_path()}/collections")
            if resp.status_code == 200:
                return [c["name"] for c in resp.json()]
            return []
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
            
    # For document operations, use /api/v2/tenants/.../collections/{id}/...
    def _doc_url(self, col_id: str, action: str) -> str:
        return f"{self._get_base_path()}/collections/{col_id}/{action}"

    def add_documents(
        self,
        collection_name: str,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        """添加文档"""
        collection = self.get_collection(collection_name)
        if not collection:
            return

        col_id = collection["id"]
        payload = {
            "ids": ids,
            "documents": documents,
        }
        if metadatas:
            payload["metadatas"] = metadatas
        if embeddings:
            payload["embeddings"] = embeddings
            
        try:
            resp = self.client.post(self._doc_url(col_id, "add"), json=payload)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to add documents to {collection_name}: {e}")

    def query(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 5,
        where: Optional[Dict] = None,
    ) -> Dict:
        """查询文档"""
        collection = self.get_collection(collection_name)
        if not collection:
            return {}
            
        col_id = collection["id"]
        payload = {
            "n_results": n_results,
        }
        if query_texts:
            payload["query_texts"] = query_texts
        if query_embeddings:
            payload["query_embeddings"] = query_embeddings
        if where:
            payload["where"] = where
            
        try:
            resp = self.client.post(self._doc_url(col_id, "query"), json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception as e:
            logger.error(f"Failed to query {collection_name}: {e}")
            return {}

    def get_documents(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict:
        """
        获取文档 (替代 collection.get())
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return {}
            
        col_id = collection["id"]
        payload = {}
        if ids: payload["ids"] = ids
        if where: payload["where"] = where
        if limit: payload["limit"] = limit
        if offset: payload["offset"] = offset
        
        try:
            resp = self.client.post(self._doc_url(col_id, "get"), json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception as e:
            logger.error(f"Failed to get documents from {collection_name}: {e}")
            return {}

    def get_by_ids(self, collection_name: str, ids: List[str]) -> Dict:
        """根据 ID 获取文档"""
        return self.get_documents(collection_name, ids=ids)

    def count(self, collection_name: str) -> int:
        """获取文档数量"""
        collection = self.get_collection(collection_name)
        if not collection:
            return 0
        
        col_id = collection["id"]
        try:
            # In V2, count might be GET /api/v2/collections/{id}/count
            resp = self.client.get(self._doc_url(col_id, "count"))
            if resp.status_code == 200:
                return resp.json()
            return 0
        except Exception:
            return 0
            
    def update_documents(self, collection_name: str, ids: List[str], documents: Optional[List[str]] = None, metadatas: Optional[List[Dict]] = None) -> None:
        """更新文档"""
        collection = self.get_collection(collection_name)
        if not collection: return
        
        col_id = collection["id"]
        payload = {"ids": ids}
        if documents: payload["documents"] = documents
        if metadatas: payload["metadatas"] = metadatas
        
        try:
            self.client.post(self._doc_url(col_id, "update"), json=payload)
        except Exception as e:
            logger.error(f"Update failed: {e}")

    def delete_documents(self, collection_name: str, ids: List[str]) -> None:
        """删除文档"""
        collection = self.get_collection(collection_name)
        if not collection: return
        
        col_id = collection["id"]
        try:
            self.client.post(self._doc_url(col_id, "delete"), json={"ids": ids})
        except Exception as e:
            logger.error(f"Delete failed: {e}")

    def reset(self) -> None:
        """重置数据库"""
        try:
            self.client.post("/api/v2/reset")
        except Exception:
            pass

# 全局实例
chroma_client = ChromaClient.get_instance()

