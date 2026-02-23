
from typing import List, Dict, Optional
import json
from loguru import logger
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings
from app.services.smart_ops.vector_store import VectorStore
from app.core.ai_client import get_ai_manager, AIModule

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

    async def analyze_root_cause(self, error_msg: str, context: Optional[str] = None) -> Dict[str, str]:
        """
        Use LLM to analyze the error message and context to deduce the root cause and a suggested fix.
        """
        ai_manager = get_ai_manager()
        
        system_prompt = (
            "You are a Senior QA Automation Engineer troubleshooting test failures. "
            "You will be given an error message from a failed test run, and optionally some context. "
            "Your task is to analyze the error and provide:\n"
            "1. root_cause: A concise explanation of why the test failed.\n"
            "2. suggested_fix: A concise recommendation on how to fix it.\n"
            "Output MUST be in valid JSON format with keys 'root_cause' and 'suggested_fix'."
        )
        
        user_content = f"Error Message:\n{error_msg}\n"
        if context:
            user_content += f"\nContext (e.g., Code Snippet, DOM Context, Action History):\n{context}"
            
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        try:
            logger.info("Requesting Defect Root Cause Analysis from AI...")
            response = await ai_manager.invoke(AIModule.DEFECT_ROOT_CAUSE, messages)
            
            # Extract JSON from response. Handle potential markdown formatting.
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
                
            analysis_dict = json.loads(content.strip())
            
            root_cause = analysis_dict.get("root_cause", "Analysis incomplete")
            suggested_fix = analysis_dict.get("suggested_fix", "No fix suggested")
            
            return {
                "root_cause": root_cause,
                "suggested_fix": suggested_fix
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze defect root cause: {e}")
            return {
                "root_cause": f"AI Analysis Failed: {str(e)}",
                "suggested_fix": "Please investigate manually."
            }
