"""
ChromaDB 向量数据库客户端

用于存储和检索 API 文档向量
"""

from typing import Optional
import chromadb
from chromadb.config import Settings


class ChromaClient:
    """
    ChromaDB 客户端封装
    
    提供向量存储和检索功能
    """
    
    _instance: Optional["ChromaClient"] = None
    
    def __init__(self, persist_dir: str = "./data/chroma"):
        """
        初始化 ChromaDB 客户端
        
        Args:
            persist_dir: 持久化目录
        """
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
    
    @classmethod
    def get_instance(cls, persist_dir: str = "./data/chroma") -> "ChromaClient":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(persist_dir)
        return cls._instance
    
    def get_collection(self, name: str) -> chromadb.Collection:
        """
        获取或创建集合
        
        Args:
            name: 集合名称
        
        Returns:
            ChromaDB Collection
        """
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def delete_collection(self, name: str) -> bool:
        """
        删除集合
        
        Args:
            name: 集合名称
        
        Returns:
            是否删除成功
        """
        try:
            self.client.delete_collection(name)
            return True
        except Exception:
            return False
    
    def list_collections(self) -> list[str]:
        """列出所有集合"""
        return [c.name for c in self.client.list_collections()]
    
    def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> None:
        """
        添加文档到集合
        
        Args:
            collection_name: 集合名称
            ids: 文档 ID 列表
            documents: 文档内容列表
            metadatas: 元数据列表
            embeddings: 向量列表（可选，不提供则自动生成）
        """
        collection = self.get_collection(collection_name)
        
        kwargs = {
            "ids": ids,
            "documents": documents,
        }
        if metadatas:
            kwargs["metadatas"] = metadatas
        if embeddings:
            kwargs["embeddings"] = embeddings
        
        collection.add(**kwargs)
    
    def query(
        self,
        collection_name: str,
        query_texts: list[str],
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> dict:
        """
        查询相似文档
        
        Args:
            collection_name: 集合名称
            query_texts: 查询文本列表
            n_results: 返回结果数量
            where: 过滤条件
        
        Returns:
            查询结果
        """
        collection = self.get_collection(collection_name)
        
        kwargs = {
            "query_texts": query_texts,
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        
        return collection.query(**kwargs)
    
    def get_by_ids(
        self,
        collection_name: str,
        ids: list[str],
    ) -> dict:
        """
        根据 ID 获取文档
        
        Args:
            collection_name: 集合名称
            ids: 文档 ID 列表
        
        Returns:
            文档数据
        """
        collection = self.get_collection(collection_name)
        return collection.get(ids=ids)
    
    def update_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """
        更新文档
        
        Args:
            collection_name: 集合名称
            ids: 文档 ID 列表
            documents: 新文档内容
            metadatas: 新元数据
        """
        collection = self.get_collection(collection_name)
        
        kwargs = {"ids": ids}
        if documents:
            kwargs["documents"] = documents
        if metadatas:
            kwargs["metadatas"] = metadatas
        
        collection.update(**kwargs)
    
    def delete_documents(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        """
        删除文档
        
        Args:
            collection_name: 集合名称
            ids: 文档 ID 列表
        """
        collection = self.get_collection(collection_name)
        collection.delete(ids=ids)
    
    def count(self, collection_name: str) -> int:
        """
        获取集合中的文档数量
        
        Args:
            collection_name: 集合名称
        
        Returns:
            文档数量
        """
        collection = self.get_collection(collection_name)
        return collection.count()
    
    def reset(self) -> None:
        """重置数据库（删除所有数据）"""
        self.client.reset()


# 全局实例
chroma_client = ChromaClient.get_instance()
