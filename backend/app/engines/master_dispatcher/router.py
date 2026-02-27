"""
Master Router
Implements the Hybrid Routing Strategy (Heuristic Fast Path -> Semantic AI Fallback).
"""
import json
import hashlib
from typing import Dict, Any
from loguru import logger
from app.engines.master_dispatcher.semantic_agent import SemanticRouterAgent

# Simple bounded cache to prevent unbounded memory growth
class BoundedCache:
    def __init__(self, maxsize: int = 1000):
        self.cache: Dict[str, str] = {}
        self.maxsize = maxsize
        
    def get(self, key: str) -> str:
        return self.cache.get(key)
        
    def set(self, key: str, value: str):
        if len(self.cache) >= self.maxsize:
            # Pop the oldest item (in Python 3.7+, dicts maintain insertion order)
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = value

routing_cache = BoundedCache()

class MasterRouter:
    def __init__(self):
        self.ai_agent = SemanticRouterAgent()

    async def route(self, step: Dict[str, Any]) -> str:
        """
        Routes the step through the Fast/Slow paths.
        Returns: "LEFT_PUPIL", "RIGHT_PUPIL", or "UNKNOWN"
        """
        step_signature = self._get_step_hash(step)
        
        # 0. Cache Hit (L3)
        cached_decision = routing_cache.get(step_signature)
        if cached_decision:
            logger.debug(f"⚡ [MasterRouter] Cache Hit for step: {cached_decision}")
            return cached_decision

        # 1. Fast Path (L1 - Heuristic Analysis)
        decision = self._heuristic_analysis(step)
        if decision != "UNKNOWN":
            logger.debug(f"⚡ [MasterRouter] Fast Path Rule Matched: {decision}")
            return decision

        # 2. Slow Path (L2 - Semantic AI Analysis)
        logger.info(f"🤔 [MasterRouter] Ambiguous step detected. Routing to Semantic Agent...")
        ai_decision = await self.ai_agent.analyze(step)
        final_decision = ai_decision.get("engine_type", "UNKNOWN")
        
        logger.info(f"🧠 [MasterRouter] Semantic Agent decided: {final_decision} (Reasoning: {ai_decision.get('reasoning')})")
        
        # 3. Update Cache
        if final_decision != "UNKNOWN":
            routing_cache.set(step_signature, final_decision)
        
        return final_decision

    def _get_step_hash(self, step: Dict[str, Any]) -> str:
        """Create a deterministic hash of the critical step fields for caching."""
        # Only hash fields that impact routing
        critical_fields = {
            "step_type": step.get("step_type"),
            "action": step.get("action"),
            "url": step.get("url"),
            "description": step.get("description"),
            "name": step.get("name"),
            "method": step.get("method"),
            "selector": step.get("selector"),
            "xpath": step.get("xpath")
        }
        step_str = json.dumps(critical_fields, sort_keys=True)
        return hashlib.md5(step_str.encode()).hexdigest()

    def _heuristic_analysis(self, step: Dict[str, Any]) -> str:
        """
        L1 Fast Path matching based on explicit fields and regex/keywords.
        """
        # 1. Explicit Declarations
        st = step.get("step_type")
        if st == "API": return "LEFT_PUPIL"
        if st == "UI": return "RIGHT_PUPIL"

        # 2. Feature Sniffing
        action = str(step.get("action", "")).lower()
        url = str(step.get("url", "")).lower()
        method = str(step.get("method", "")).upper()

        # Left Pupil (API Engine) Signatures
        if method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            return "LEFT_PUPIL"
        if url.startswith("http") and ("/api/" in url or "graphql" in url):
            return "LEFT_PUPIL"
        if "headers" in step or "json_body" in step or "assertions" in step or "extract" in step:
            # It's an API request structure
            return "LEFT_PUPIL"

        # Right Pupil (UI Engine) Signatures
        ui_keywords = ["click", "type", "hover", "scroll", "screenshot", "navigate", "assert_visible", "wait_for"]
        if any(keyword in action for keyword in ui_keywords):
            return "RIGHT_PUPIL"
        if step.get("selector") or step.get("xpath"):
            return "RIGHT_PUPIL"
            
        # Description sniffing (very obvious keywords)
        desc = str(step.get("description", "")).lower()
        if "click" in desc or "type into" in desc or "button" in desc:
            return "RIGHT_PUPIL"
        if "request" in desc and "status code" in desc:
            return "LEFT_PUPIL"

        return "UNKNOWN"
