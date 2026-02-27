"""
Librarian Tool - Right Pupil V2.5
Wrapper for KnowledgeRetriever to be used as an AutoGen tool.
"""

from typing import Annotated
from loguru import logger

def search_knowledge_base(
    query: Annotated[str, "The search query to look up in the knowledge base, e.g., 'Login button locator' or 'Error code 500'"],
    project_id: Annotated[str, "Project ID (optional). Defaults to 'default'"] = "default"
) -> str:
    """
    Retrieves historical context, known bugs, or application documentation from the vector database.
    """
    import asyncio
    import nest_asyncio
    from app.services.left_pupil.knowledge_retriever import KnowledgeRetriever
    
    nest_asyncio.apply()
    
    kr = KnowledgeRetriever()
    
    # Since AutoGen usually runs this in a thread executor, we can use asyncio.run
    try:
        loop = asyncio.get_event_loop()
    except Exception:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        contexts = loop.run_until_complete(kr.retrieve(query, project_id))
    except Exception as e:
        logger.error(f"Librarian tool failed: {e}")
        return f"Error connecting to knowledge base: {e}"
        
    if not contexts:
        return "No relevant knowledge found."
        
    return "\n---\n".join([f"[Source: {c.metadata.get('source', 'Unknown')}] {c.content}" for c in contexts])
