from __future__ import annotations

import pytest


def _legacy_payload() -> dict:
    return {
        "name": "legacy-compat-case",
        "description": "legacy payload",
        "mode": "UI",
        "priority": "P1",
        "steps": [{"action": "open", "target": "https://example.com"}],
        "tags": ["legacy"],
    }


@pytest.mark.asyncio
async def test_legacy_create_payload_still_works(client) -> None:
    response = await client.post("/api/v1/test-cases", json=_legacy_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "legacy-compat-case"
    assert body["mode"] == "UI"
    assert body["status"] in {"draft", "active", "disabled", "archived"}


@pytest.mark.asyncio
async def test_legacy_list_response_shape_still_works(client) -> None:
    await client.post("/api/v1/test-cases", json=_legacy_payload())
    response = await client.get("/api/v1/test-cases?page=1&page_size=100")
    assert response.status_code == 200

    body = response.json()
    assert set(["items", "total", "page", "page_size"]).issubset(body.keys())
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_legacy_get_and_put_flow_still_works(client) -> None:
    created = await client.post("/api/v1/test-cases", json=_legacy_payload())
    assert created.status_code == 201
    tc_id = created.json()["id"]

    fetched = await client.get(f"/api/v1/test-cases/{tc_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == tc_id

    update_payload = _legacy_payload()
    update_payload["name"] = "legacy-compat-case-updated"
    updated = await client.put(f"/api/v1/test-cases/{tc_id}", json=update_payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "legacy-compat-case-updated"


@pytest.mark.asyncio
async def test_flat_legacy_api_payload_is_returned_with_v2_shape(client) -> None:
    payload = {
        "name": "flat-api-legacy-case",
        "description": "flat api payload",
        "mode": "API",
        "priority": "P1",
        "steps": [
            {
                "id": "STEP_LEGACY",
                "step_type": "API",
                "method": "POST",
                "url": "http://example.test/users",
                "headers": {"Content-Type": "application/json"},
                "body": {"name": "Ada"},
                "expected_status_code": 201,
                "json_assertions": {"$.id": "123"},
                "extract": {"user_id": "$.id"},
            }
        ],
        "tags": ["legacy", "api"],
    }

    created = await client.post("/api/v1/test-cases", json=payload)
    assert created.status_code == 201
    step = created.json()["steps"][0]
    assert step["protocol"] == "API-IR"
    assert step["request"]["method"] == "POST"
    assert step["request"]["url"] == "http://example.test/users"
    assert step["assertion"]["status_code"] == 201
    assert step["assertion"]["json_assertions"] == {"$.id": "123"}
    assert step["extraction"] == {"user_id": "$.id"}
    assert step["method"] == "POST"
    assert step["expected_status_code"] == 201


@pytest.mark.asyncio
async def test_frontend_like_query_patterns_remain_compatible(client) -> None:
    await client.post("/api/v1/test-cases", json=_legacy_payload())

    # Pattern used by frontend services: page/page_size/mode/status/tag query combinations.
    response = await client.get(
        "/api/v1/test-cases?page=1&page_size=20&mode=UI&status=draft&tag=legacy"
    )
    assert response.status_code == 200
