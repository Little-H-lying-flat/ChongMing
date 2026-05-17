
from typing import List, Dict, Optional
import json
from loguru import logger
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
from app.services.smart_ops.vector_store import VectorStore
from app.core.ai_client import get_ai_manager, AIModule, Message
from app.services.smart_ops.diagnostic_room import run_diagnostic_chat

class DefectManager:
    """
    缺陷分析管理器 (Defect Manager)
    
    Integrates AI (Embeddings) with Vector DB (Milvus) 
    to enable semantic search for similar defects.
    """
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.embeddings: OpenAIEmbeddings | None = None

    def _get_embeddings(self) -> OpenAIEmbeddings | None:
        if self.embeddings is not None:
            return self.embeddings
        if not settings.QWEN_API_KEY:
            logger.warning("Embedding search disabled because QWEN_API_KEY is not configured")
            return None
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.QWEN_API_KEY,
            openai_api_base=settings.QWEN_BASE_URL,
            model=settings.MODEL_EMBEDDING,
        )
        return self.embeddings

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
            embeddings = self._get_embeddings()
            if embeddings is None:
                return
            text_to_embed = f"{error_msg}\nRoot Cause: {root_cause}"
            vector = await embeddings.aembed_query(text_to_embed)

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
            embeddings = self._get_embeddings()
            if embeddings is None:
                return []
            vector = await embeddings.aembed_query(error_msg)
            results = self.vector_store.search(vector, top_k=top_k)
            return results
        except Exception as e:
            logger.error(f"Failed to find similar defects: {e}")
            return []

    async def analyze_root_cause(self, error_msg: str, context: Optional[str] = None) -> Dict[str, str]:
        """
        Use AutoGen Multi-Agent Diagnostic Room to analyze the error message and context.
        """
        try:
            logger.info("Requesting Defect Root Cause Analysis from Joint Diagnostic Room (AutoGen)...")
            
            # Call the new GroupChat
            final_json_str = await run_diagnostic_chat(error_msg=error_msg, context=context)
            
            # Extract JSON from response. Handle potential markdown formatting.
            content = final_json_str.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
                
            analysis_dict = json.loads(content.strip())
            
            root_cause = analysis_dict.get("root_cause", "分析未完成或格式不正确")
            suggested_fix = analysis_dict.get("suggested_fix", "未提供修复建议")
            
            return {
                "root_cause": root_cause,
                "suggested_fix": suggested_fix
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Diagnostic Room output: {e}\nRaw Output: {final_json_str}")
            return {
                "root_cause": "多智能体会诊完成，但输出的 JSON 格式解析失败",
                "suggested_fix": f"原始诊断输出:\n{final_json_str}"
            }
        except Exception as e:
            logger.error(f"Failed to analyze defect root cause: {e}")
            return {
                "root_cause": f"AI 多专家联合诊断调用失败：{str(e)}",
                "suggested_fix": "请检查后端日志，或进行人工排查。"
            }
