from app.services.api_case_ir_converter import normalize_api_case_payload_v2, normalize_api_step_v2


def test_normalizes_flat_legacy_api_step_to_v2_and_aliases():
    step = {
        "id": "STEP_1",
        "step_type": "API",
        "method": "post",
        "url": "http://example.test/users",
        "headers": {"X-Test": "1"},
        "body": {"name": "Ada"},
        "expected_status_code": 201,
        "json_assertions": {"$.id": "123"},
        "extract": {"user_id": "$.id"},
    }

    normalized = normalize_api_step_v2(step)

    assert normalized["protocol"] == "API-IR"
    assert normalized["version"] == "2.0"
    assert normalized["request"]["method"] == "POST"
    assert normalized["request"]["url"] == "http://example.test/users"
    assert normalized["request"]["headers"] == {"X-Test": "1"}
    assert normalized["assertion"]["status_code"] == 201
    assert normalized["assertion"]["json_assertions"] == {"$.id": "123"}
    assert normalized["extraction"] == {"user_id": "$.id"}
    assert normalized["method"] == "POST"
    assert normalized["expected_status_code"] == 201
    assert normalized["extract"] == {"user_id": "$.id"}
    assert {"type": "status_code", "expected": 201} in normalized["assertions"]
    assert {"type": "jsonpath", "path": "$.id", "expected": "123", "operator": "equals"} in normalized["assertions"]


def test_normalizes_nested_only_design_step_to_flat_aliases():
    step = {
        "id": "STEP_2",
        "step_type": "API",
        "name": "Fetch profile",
        "request": {
            "method": "GET",
            "url": "http://example.test/profile",
            "headers": {"Authorization": "Bearer ${token}"},
            "query_params": {"verbose": True},
            "timeout_ms": 10000,
        },
        "assertion": {
            "status_code": 200,
            "json_assertions": {"$.email": "test@example.com"},
        },
        "extraction": {"profile_id": "$.id"},
    }

    normalized = normalize_api_step_v2(step)

    assert normalized["url"] == "http://example.test/profile"
    assert normalized["method"] == "GET"
    assert normalized["headers"] == {"Authorization": "Bearer ${token}"}
    assert normalized["query_params"] == {"verbose": True}
    assert normalized["timeout_ms"] == 10000
    assert normalized["expected_status_code"] == 200
    assert normalized["json_assertions"] == {"$.email": "test@example.com"}
    assert normalized["extract"] == {"profile_id": "$.id"}


def test_path_and_base_url_ref_create_variable_url_alias():
    step = {
        "step_type": "API",
        "request": {
            "method": "GET",
            "path": "api/v1/ping",
            "base_url_ref": "base_url",
        },
        "assertion": {"status_code": 200},
    }

    normalized = normalize_api_step_v2(step)

    assert normalized["url"] == "${base_url}/api/v1/ping"
    assert normalized["request"]["path"] == "api/v1/ping"
    assert normalized["request"]["base_url_ref"] == "base_url"


def test_array_extraction_keeps_v2_rules_and_maps_body_rules_to_executor_extract():
    step = {
        "step_type": "API",
        "method": "GET",
        "url": "http://example.test/session",
        "extraction": [
            {"name": "token", "from": "body", "path": "$.token"},
            {"name": "set_cookie", "from": "header", "path": "Set-Cookie"},
        ],
    }

    normalized = normalize_api_step_v2(step)

    assert normalized["extraction"] == step["extraction"]
    assert normalized["extract"] == {"token": "$.token"}


def test_ui_step_is_not_modified():
    step = {"step_type": "UI", "action": "click", "target": "#submit"}

    normalized = normalize_api_step_v2(step, mode_hint="HYBRID")

    assert normalized == step


def test_case_payload_normalizes_only_api_steps():
    payload = {
        "mode": "HYBRID",
        "steps": [
            {"step_type": "UI", "action": "open", "target": "http://example.test"},
            {"step_type": "API", "method": "GET", "url": "http://example.test/api", "expected_status_code": 200},
        ],
    }

    normalized = normalize_api_case_payload_v2(payload)

    assert normalized["steps"][0] == payload["steps"][0]
    assert normalized["steps"][1]["protocol"] == "API-IR"
    assert normalized["steps"][1]["request"]["url"] == "http://example.test/api"
