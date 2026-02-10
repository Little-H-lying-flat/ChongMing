"""
API 文档向量摄入器

将 API 文档向量化存储到 ChromaDB
"""

import hashlib
from typing import Optional
from dataclasses import dataclass, field

from app.core.chroma_client import ChromaClient
from app.services.left_pupil.swagger_parser import SwaggerParser, ApiEndpoint


@dataclass
class ApiChunk:
    """API 文档切片"""
    chunk_id: str
    content: str
    metadata: dict = field(default_factory=dict)


class SpecIngestor:
    """
    API 文档摄入器
    
    将 API 文档切片并向量化存储到 ChromaDB
    """
    
    COLLECTION_PREFIX = "api_specs_"
    
    def __init__(self, chroma_client: Optional[ChromaClient] = None):
        """
        初始化摄入器
        
        Args:
            chroma_client: ChromaDB 客户端
        """
        self.chroma = chroma_client or ChromaClient.get_instance()
        self.parser = SwaggerParser()
    
    def _get_collection_name(self, project_id: str) -> str:
        """获取集合名称"""
        return f"{self.COLLECTION_PREFIX}{project_id}"
    
    def ingest_file(self, file_path: str, project_id: str) -> int:
        """
        从文件摄入 API 文档
        
        Args:
            file_path: 文件路径
            project_id: 项目 ID
        
        Returns:
            摄入的文档数量
        """
        endpoints = self.parser.parse_file(file_path)
        return self._ingest_endpoints(endpoints, project_id)
    
    def ingest_url(self, url: str, project_id: str) -> int:
        """
        从 URL 摄入 API 文档
        
        Args:
            url: Swagger 文档 URL
            project_id: 项目 ID
        
        Returns:
            摄入的文档数量
        """
        endpoints = self.parser.parse_url(url)
        return self._ingest_endpoints(endpoints, project_id)
    
    def ingest_spec(self, spec: dict, project_id: str) -> int:
        """
        从字典摄入 API 文档
        
        Args:
            spec: OpenAPI/Swagger 规范字典
            project_id: 项目 ID
        
        Returns:
            摄入的文档数量
        """
        endpoints = self.parser.parse(spec)
        return self._ingest_endpoints(endpoints, project_id)
    
    def _ingest_endpoints(self, endpoints: list[ApiEndpoint], project_id: str) -> int:
        """摄入端点列表"""
        if not endpoints:
            return 0
        
        collection_name = self._get_collection_name(project_id)
        chunks = [self._endpoint_to_chunk(ep) for ep in endpoints]
        
        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        
        self.chroma.add_documents(
            collection_name=collection_name,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        
        return len(chunks)
    
    def _endpoint_to_chunk(self, endpoint: ApiEndpoint) -> ApiChunk:
        """将端点转换为切片"""
        # 生成唯一 ID
        chunk_id = hashlib.md5(endpoint.id.encode()).hexdigest()[:12]
        
        # 生成可搜索内容
        content = endpoint.to_searchable_text()
        
        # 构建元数据
        required_params = [p.name for p in endpoint.parameters if p.required]
        output_fields = self._extract_output_fields(endpoint)
        
        metadata = {
            "endpoint_id": endpoint.id,
            "path": endpoint.path,
            "method": endpoint.method,
            "summary": endpoint.summary[:200] if endpoint.summary else "",
            "tags": ",".join(endpoint.tags),
            "requires_auth": len(endpoint.security) > 0,
            "has_request_body": endpoint.request_body is not None,
            "required_params": ",".join(required_params),
            "output_fields": ",".join(output_fields),
            "deprecated": endpoint.deprecated,
        }
        
        return ApiChunk(
            chunk_id=chunk_id,
            content=content,
            metadata=metadata,
        )
    
    def _extract_output_fields(self, endpoint: ApiEndpoint) -> list[str]:
        """提取响应字段"""
        fields = []
        
        # 查找成功响应 (2xx)
        for status_code, response in endpoint.responses.items():
            if status_code.startswith("2"):
                schema = response.schema
                if "properties" in schema:
                    fields.extend(schema["properties"].keys())
                break
        
        return fields[:10]  # 限制数量
    
    def search(
        self,
        query: str,
        project_id: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """
        搜索相关 API
        
        Args:
            query: 查询文本
            project_id: 项目 ID
            top_k: 返回数量
            filters: 过滤条件
        
        Returns:
            搜索结果列表
        """
        collection_name = self._get_collection_name(project_id)
        
        results = self.chroma.query(
            collection_name=collection_name,
            query_texts=[query],
            n_results=top_k,
            where=filters,
        )
        
        # 格式化结果
        formatted = []
        if results and results.get("ids"):
            ids = results["ids"][0]
            documents = results["documents"][0] if results.get("documents") else []
            metadatas = results["metadatas"][0] if results.get("metadatas") else []
            distances = results["distances"][0] if results.get("distances") else []
            
            for i, chunk_id in enumerate(ids):
                formatted.append({
                    "chunk_id": chunk_id,
                    "content": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else 0,
                    "relevance": 1 - (distances[i] if i < len(distances) else 0),
                })
        
        return formatted
    
    def get_endpoint_by_id(self, endpoint_id: str, project_id: str) -> Optional[dict]:
        """
        根据端点 ID 获取文档
        
        Args:
            endpoint_id: 端点 ID (如 "POST /api/v1/orders")
            project_id: 项目 ID
        
        Returns:
            端点文档
        """
        collection_name = self._get_collection_name(project_id)
        chunk_id = hashlib.md5(endpoint_id.encode()).hexdigest()[:12]
        
        results = self.chroma.get_by_ids(collection_name, [chunk_id])
        
        if results and results.get("ids"):
            return {
                "chunk_id": results["ids"][0],
                "content": results["documents"][0] if results.get("documents") else "",
                "metadata": results["metadatas"][0] if results.get("metadatas") else {},
            }
        return None
    
    def list_endpoints(self, project_id: str, limit: int = 100) -> list[dict]:
        """
        列出项目的所有端点
        
        Args:
            project_id: 项目 ID
            limit: 限制数量
        
        Returns:
            端点列表
        """
        collection_name = self._get_collection_name(project_id)
        collection = self.chroma.get_collection(collection_name)
        
        results = collection.get(limit=limit)
        
        endpoints = []
        if results:
            ids = results.get("ids", [])
            metadatas = results.get("metadatas", [])
            
            for i, chunk_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                endpoints.append({
                    "chunk_id": chunk_id,
                    "endpoint_id": meta.get("endpoint_id", ""),
                    "method": meta.get("method", ""),
                    "path": meta.get("path", ""),
                    "summary": meta.get("summary", ""),
                })
        
        return endpoints
    
    def delete_project(self, project_id: str) -> bool:
        """
        删除项目的所有 API 文档
        
        Args:
            project_id: 项目 ID
        
        Returns:
            是否删除成功
        """
        collection_name = self._get_collection_name(project_id)
        return self.chroma.delete_collection(collection_name)
    
    def count(self, project_id: str) -> int:
        """
        获取项目的文档数量
        
        Args:
            project_id: 项目 ID
        
        Returns:
            文档数量
        """
        collection_name = self._get_collection_name(project_id)
        return self.chroma.count(collection_name)
