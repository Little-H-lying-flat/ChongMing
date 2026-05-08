"""
Long-term memory wrapper for Mem0.

Provides tenant/project scoped memory with graceful degradation:
- lazy initialization (only on first use)
- configurable enable/disable switch
- no-op fallback when Mem0/storage is unavailable
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger

try:
    from mem0 import Memory as Mem0Memory
except Exception as exc:  # pragma: no cover - depends on optional runtime package
    Mem0Memory = None
    _MEM0_IMPORT_ERROR: Optional[Exception] = exc
else:
    _MEM0_IMPORT_ERROR = None


class MemoryBase:
    _instance: Optional["MemoryBase"] = None

    def __new__(cls) -> "MemoryBase":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.memory = None
            cls._instance._initialized = False
            cls._instance._available = False
        return cls._instance

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._init_memory()

    def _build_db_path(self) -> str:
        if settings.MEM0_QDRANT_PATH:
            return settings.MEM0_QDRANT_PATH

        is_test = "test" in str(settings.DATABASE_URL) or "memory" in str(settings.DATABASE_URL)
        base_path = "./mem0_qdrant_db_test" if is_test else "./mem0_qdrant_db"

        # Isolate pytest workers/processes to reduce SQLite lock contention.
        if os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
            return str(Path(base_path) / f"pytest_{os.getpid()}")
        return base_path

    def _init_memory(self) -> None:
        self._initialized = True

        if not settings.MEM0_ENABLED:
            logger.info("Mem0 disabled via MEM0_ENABLED=false; memory features run in no-op mode.")
            self.memory = None
            self._available = False
            return

        if Mem0Memory is None:
            logger.warning(f"Mem0 import unavailable: {_MEM0_IMPORT_ERROR}. Running in no-op mode.")
            self.memory = None
            self._available = False
            return

        db_path = self._build_db_path()
        Path(db_path).mkdir(parents=True, exist_ok=True)
        embedding_model = settings.MODEL_EMBEDDING
        embedding_dims = settings.MEM0_EMBEDDING_DIMS
        collection_name = f"chongming_mem0_{embedding_dims}"

        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": settings.QWEN_API_KEY,
                    "model": settings.MODEL_GENERAL_CHAT,
                    "openai_base_url": settings.QWEN_BASE_URL,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "api_key": settings.QWEN_API_KEY,
                    "model": embedding_model,
                    "embedding_dims": embedding_dims,
                    "openai_base_url": settings.QWEN_BASE_URL,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": collection_name,
                    "embedding_model_dims": embedding_dims,
                    "path": db_path,
                },
            },
        }

        try:
            self.memory = Mem0Memory.from_config(config)
            self._available = True
            logger.info(f"Mem0 initialized successfully (path={db_path}).")
        except Exception as exc:
            msg = str(exc)
            if "WinError 32" in msg or "locked" in msg.lower():
                logger.warning(
                    "Mem0 storage is locked by another process; falling back to no-op mode for this process."
                )
            else:
                logger.warning(f"Mem0 unavailable at startup; running in no-op mode. reason={exc}")
            self.memory = None
            self._available = False

    def add_memory(
        self,
        content: str,
        user_id: str,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Add memory scoped to user/project."""
        self._ensure_initialized()
        if not self.memory:
            return None

        metadata: Dict[str, Any] = {}
        if project_id:
            metadata["project_id"] = project_id
        if session_id:
            metadata["session_id"] = session_id

        try:
            res = self.memory.add(
                messages=[{"role": "user", "content": content}],
                user_id=user_id,
                metadata=metadata,
            )
            logger.info(
                f"Memory added for user={user_id}, project={project_id}, content={content[:50]}..."
            )
            return res
        except Exception as exc:
            logger.error(f"Failed to add memory: {exc}")
            return None

    def search_memory(
        self,
        query: str,
        user_id: str,
        project_id: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """Search memory and return a formatted context string."""
        self._ensure_initialized()
        if not self.memory:
            return ""

        filters: Dict[str, Any] = {}
        if project_id:
            filters["project_id"] = project_id

        try:
            results = self.memory.search(
                query=query,
                user_id=user_id,
                limit=limit,
                filters=filters if filters else None,
            )
            if not results:
                return ""

            memories = [r["memory"] for r in results if "memory" in r]
            combined = "\n- ".join(memories)
            if combined:
                return "【历史经验与偏好参考】\n- " + combined
            return ""
        except Exception as exc:
            logger.error(f"Failed to search memory: {exc}")
            return ""


# Global singleton
memory_base = MemoryBase()
