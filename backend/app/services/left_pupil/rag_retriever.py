"""
RAG 检索器

基于向量检索的 API 意图匹配
"""

from typing import Optional
from dataclasses import dataclass, field
import httpx

from app.core.config import settings
from app.services.left_pupil.spec_ingestor import SpecIngestor


@dataclass
class ApiContext:
    """API 上下文"""
    endpoint_id: str
    method: str
    path: str
    summary: str
    content: str
    metadata: dict
    relevance: float = 0.0


class RagRetriever:
    """
    RAG 检索器
    
    通过意图扩展和向量检索找到相关 API
    """
    
    def __init__(self, ingestor: Optional[SpecIngestor] = None):
        """
        初始化检索器
        
        Args:
            ingestor: API 文档摄入器
        """
        self.ingestor = ingestor or SpecIngestor()
        self._llm_client = None
    
    @property
    def llm_client(self):
        """延迟初始化 LLM 客户端"""
        if self._llm_client is None:
            self._llm_client = httpx.AsyncClient(
                base_url=settings.QWEN_BASE_URL,
                headers={"Authorization": f"Bearer {settings.QWEN_API_KEY}"},
                timeout=30.0,
            )
        return self._llm_client
    
    async def retrieve(
        self,
        intent: str,
        project_id: str,
        top_k: int = 5,
        expand_intent: bool = True,
    ) -> list[ApiContext]:
        """
        检索相关 API
        
        Args:
            intent: 用户意图
            project_id: 项目 ID
            top_k: 返回数量
            expand_intent: 是否扩展意图
        
        Returns:
            相关 API 列表
        """
        # 1. 意图扩展
        queries = [intent]
        if expand_intent:
            expanded = await self._expand_intent(intent)
            queries.extend(expanded)
        
        # 2. 多查询检索
        all_results = []
        for query in queries[:5]:  # 限制查询数量
            results = self.ingestor.search(
                query=query,
                project_id=project_id,
                top_k=top_k,
            )
            all_results.extend(results)
        
        # 3. 去重与排序
        unique_results = self._dedupe_and_rank(all_results)
        
        # 4. 转换为 ApiContext
        contexts = []
        for result in unique_results[:top_k]:
            meta = result.get("metadata", {})
            contexts.append(ApiContext(
                endpoint_id=meta.get("endpoint_id", ""),
                method=meta.get("method", ""),
                path=meta.get("path", ""),
                summary=meta.get("summary", ""),
                content=result.get("content", ""),
                metadata=meta,
                relevance=result.get("relevance", 0),
            ))
        
        return contexts
    
    async def _expand_intent(self, intent: str) -> list[str]:
        """
        扩展用户意图
        
        使用 LLM 生成同义词和相关词
        """
        prompt = f"""请将以下用户意图扩展为多个相关的搜索词（中英文均可）。
只输出 JSON 数组，不要其他内容。

用户意图：{intent}

输出示例：["词1", "词2", "词3"]"""

        try:
            response = await self.llm_client.post(
                "/chat/completions",
                json={
                    "model": settings.MODEL_GENERAL_CHAT,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                # 解析 JSON 数组
                import json
                return json.loads(content)
        except Exception:
            pass
        
        # 备用：简单分词
        return self._simple_expand(intent)
    
    def _simple_expand(self, intent: str) -> list[str]:
        """简单意图扩展（备用）"""
        # 基础扩展词典
        expansions = {
            "登录": ["login", "signin", "auth", "认证"],
            "注册": ["register", "signup", "创建账号"],
            "用户": ["user", "account", "member"],
            "订单": ["order", "purchase", "买"],
            "商品": ["product", "item", "goods"],
            "支付": ["pay", "payment", "checkout"],
            "查询": ["query", "get", "list", "搜索"],
            "创建": ["create", "add", "new", "post"],
            "更新": ["update", "modify", "edit", "put"],
            "删除": ["delete", "remove", "del"],
        }
        
        result = []
        for keyword, synonyms in expansions.items():
            if keyword in intent:
                result.extend(synonyms)
        
        return result[:5]
    
    def _dedupe_and_rank(self, results: list[dict]) -> list[dict]:
        """去重并按相关性排序"""
        seen = set()
        unique = []
        
        for result in results:
            chunk_id = result.get("chunk_id")
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                unique.append(result)
        
        # 按相关性降序排序
        unique.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return unique
    
    def build_context(self, apis: list[ApiContext]) -> str:
        """
        构建 LLM 上下文
        
        Args:
            apis: API 上下文列表
        
        Returns:
            格式化的上下文字符串
        """
        if not apis:
            return "【无相关 API】"
        
        lines = ["【可用 API 列表】\n"]
        
        for i, api in enumerate(apis, 1):
            lines.append(f"## API {i}: {api.method} {api.path}")
            if api.summary:
                lines.append(f"描述: {api.summary}")
            lines.append(f"详情:\n{api.content}")
            lines.append("---")
        
        return "\n".join(lines)
    
    async def close(self):
        """关闭客户端"""
        if self._llm_client:
            await self._llm_client.aclose()
