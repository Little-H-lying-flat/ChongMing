from __future__ import annotations

from copy import deepcopy
from typing import Any

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
API_PROTOCOL = "API-IR"
API_VERSION = "2.0"


def is_api_step(step: dict, mode_hint: str | None = None) -> bool:
    step_type = step.get("step_type") or step.get("type")
    if isinstance(step_type, str) and step_type.upper() == "API":
        return True

    method = step.get("method")
    if isinstance(method, str) and method.upper() in HTTP_METHODS:
        return True

    request = step.get("request")
    if isinstance(request, dict):
        request_method = request.get("method")
        if isinstance(request_method, str) and request_method.upper() in HTTP_METHODS:
            return True

    return (mode_hint or "").upper() == "API"


def normalize_api_case_payload_v2(case_data: dict) -> dict:
    normalized = dict(case_data)
    normalized["steps"] = normalize_api_steps_v2(
        normalized.get("steps") or [],
        str(normalized.get("mode") or ""),
    )
    return normalized


def normalize_api_steps_v2(steps: list, mode_hint: str | None = None) -> list:
    return [normalize_api_step_v2(step, mode_hint) if isinstance(step, dict) else step for step in steps]


def normalize_api_step_v2(step: dict, mode_hint: str | None = None) -> dict:
    if not is_api_step(step, mode_hint):
        return dict(step)

    source = deepcopy(step)
    request = dict(source.get("request") or {})
    assertion = dict(source.get("assertion") or {})
    extraction = _normalize_extraction(source.get("extraction", source.get("extract", {})))

    method = str(request.get("method") or source.get("method") or "GET").upper()
    url = request.get("url") or source.get("url") or source.get("path") or source.get("url_path") or source.get("target") or "/"
    base_url_ref = request.get("base_url_ref") or source.get("base_url_ref")
    path = request.get("path") or source.get("path")
    if not request.get("url") and path and base_url_ref:
        url = f"${{{base_url_ref}}}{_normalize_path(path)}"

    headers = request.get("headers") if "headers" in request else source.get("headers", {})
    query_params = request.get("query_params") if "query_params" in request else source.get("query_params", source.get("params", {}))
    path_params = request.get("path_params") if "path_params" in request else source.get("path_params", {})
    body = request.get("body") if "body" in request else source.get("body", source.get("json_body", source.get("input_data")))
    timeout_ms = request.get("timeout_ms") or source.get("timeout_ms") or source.get("timeout") or 30000
    content_type = request.get("content_type") or source.get("content_type") or "application/json"

    expected_status = _first_present(
        assertion.get("status_code"),
        source.get("expected_status_code"),
        source.get("status_code"),
    )
    json_assertions = assertion.get("json_assertions") or source.get("json_assertions") or {}

    normalized_request = {
        "method": method,
        "url": url,
        "headers": headers or {},
        "query_params": query_params or {},
        "path_params": path_params or {},
        "body": body,
        "timeout_ms": timeout_ms,
        "content_type": content_type,
    }
    if path:
        normalized_request["path"] = path
    if base_url_ref:
        normalized_request["base_url_ref"] = base_url_ref

    normalized_assertion = {}
    if expected_status is not None:
        normalized_assertion["status_code"] = expected_status
    if json_assertions:
        normalized_assertion["json_assertions"] = json_assertions
    for key in ("contains", "not_contains", "expression"):
        if assertion.get(key) is not None:
            normalized_assertion[key] = assertion[key]
        elif source.get(key) is not None:
            normalized_assertion[key] = source[key]

    assertions = _normalize_assertions(source.get("assertions"), expected_status, json_assertions)

    normalized = dict(source)
    normalized.update(
        {
            "protocol": API_PROTOCOL,
            "version": API_VERSION,
            "step_type": "API",
            "id": source.get("id") or source.get("step_id") or "STEP_001",
            "name": source.get("name") or source.get("description") or source.get("action") or "API Step",
            "description": source.get("description") or source.get("name") or source.get("action") or "API Step",
            "request": normalized_request,
            "assertion": normalized_assertion,
            "extraction": extraction,
            "method": method,
            "url": url,
            "headers": headers or {},
            "query_params": query_params or {},
            "path_params": path_params or {},
            "body": body,
            "timeout_ms": timeout_ms,
            "expected_status_code": expected_status,
            "json_assertions": json_assertions,
            "extract": _to_executor_extract(extraction),
            "assertions": assertions,
        }
    )
    normalized.setdefault("retry", source.get("retry") or {})
    normalized.setdefault("metadata", source.get("metadata") or {})
    return normalized


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_path(path: Any) -> str:
    value = str(path or "")
    return value if value.startswith("/") else f"/{value}"


def _normalize_extraction(extraction: Any) -> Any:
    if isinstance(extraction, dict):
        return dict(extraction)
    if isinstance(extraction, list):
        return [dict(item) if isinstance(item, dict) else item for item in extraction]
    return {}


def _to_executor_extract(extraction: Any) -> dict[str, str]:
    if isinstance(extraction, dict):
        return extraction
    if not isinstance(extraction, list):
        return {}

    result: dict[str, str] = {}
    for rule in extraction:
        if not isinstance(rule, dict):
            continue
        if rule.get("from", "body") != "body":
            continue
        name = rule.get("name")
        path = rule.get("path")
        if name and path:
            result[str(name)] = str(path)
    return result


def _normalize_assertions(existing: Any, expected_status: Any, json_assertions: Any) -> list[dict[str, Any]]:
    assertions = [dict(item) for item in existing or [] if isinstance(item, dict)]

    if expected_status is not None and not any(item.get("type") == "status_code" for item in assertions):
        assertions.append({"type": "status_code", "expected": expected_status})

    if isinstance(json_assertions, dict):
        existing_paths = {item.get("path") for item in assertions if item.get("type") == "jsonpath"}
        for path, expected in json_assertions.items():
            if path not in existing_paths:
                assertions.append({"type": "jsonpath", "path": path, "expected": expected, "operator": "equals"})

    return assertions
