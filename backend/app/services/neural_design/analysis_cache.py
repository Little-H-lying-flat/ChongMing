import hashlib
import json
import time
from typing import Any, Dict, Optional

from app.services.neural_design.models import DesignRequest


_CACHE_TTL_SECONDS = 1800
_MAX_CACHE_SIZE = 128
_analysis_cache: Dict[str, Dict[str, Any]] = {}


def _normalize_payload(request: DesignRequest) -> Dict[str, Any]:
    return {
        "project_id": request.project_id,
        "requirement_text": request.requirement_text,
        "target_type": request.target_type,
        "target_url": request.target_url or "",
        "context": request.context or "",
    }


def build_analysis_cache_key(request: DesignRequest) -> str:
    payload = _normalize_payload(request)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _prune_expired(now: Optional[float] = None) -> None:
    current = now if now is not None else time.time()
    expired_keys = [
        key for key, entry in _analysis_cache.items()
        if current - entry.get("created_at", 0) >= entry.get("ttl_seconds", _CACHE_TTL_SECONDS)
    ]
    for key in expired_keys:
        _analysis_cache.pop(key, None)


def _ensure_capacity() -> None:
    if len(_analysis_cache) < _MAX_CACHE_SIZE:
        return

    oldest_key = min(
        _analysis_cache,
        key=lambda key: _analysis_cache[key].get("created_at", 0),
    )
    _analysis_cache.pop(oldest_key, None)


def get_cached_analysis(key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    _prune_expired(now)
    entry = _analysis_cache.get(key)
    if not entry:
        return None

    # Return a deep copy so downstream code cannot mutate cache state.
    return json.loads(json.dumps(entry["value"], ensure_ascii=False))


def set_cached_analysis(
    key: str,
    value: Dict[str, Any],
    ttl_seconds: int = _CACHE_TTL_SECONDS,
) -> None:
    _prune_expired()
    _ensure_capacity()
    _analysis_cache[key] = {
        "created_at": time.time(),
        "ttl_seconds": ttl_seconds,
        "value": json.loads(json.dumps(value, ensure_ascii=False)),
    }
