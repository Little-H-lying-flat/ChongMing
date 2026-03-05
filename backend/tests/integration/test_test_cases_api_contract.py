from __future__ import annotations

import pytest


def _payload(name: str = "api-contract-case") -> dict:
    return {
        "name": name,
        "description": "contract test case",
        "mode": "API",
        "priority": "P1",
        "steps": [{"action": "call_api", "path": "/ping"}],
        "tags": ["contract", "api"],
    }


@pytest.mark.asyncio
async def test_get_list_with_legacy_filters_is_compatible(client) -> None:
    create = await client.post("/api/v1/test-cases", json=_payload())
    assert create.status_code == 201

    response = await client.get("/api/v1/test-cases?page=1&page_size=20&mode=API")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.asyncio
async def test_get_list_with_new_filters_contract(client) -> None:
    await client.post("/api/v1/test-cases", json=_payload(name="priority-p0-case"))

    response = await client.get(
        "/api/v1/test-cases?page=1&page_size=20&priority=P0&keyword=priority&owner=qa"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 0


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Pending implementation: 6-state lifecycle should accept 'review' updates",
    strict=True,
)
async def test_put_should_accept_review_state_after_lifecycle_upgrade(client) -> None:
    created = await client.post("/api/v1/test-cases", json=_payload())
    assert created.status_code == 201
    tc_id = created.json()["id"]

    update_payload = _payload(name="updated-review-case")
    update_payload["status"] = "review"
    updated = await client.put(f"/api/v1/test-cases/{tc_id}", json=update_payload)
    assert updated.status_code == 200
    assert updated.json()["status"] == "review"


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Pending implementation: delete soft-rule when case is referenced by executions",
    strict=True,
)
async def test_delete_should_block_when_referenced_by_execution(client) -> None:
    created = await client.post("/api/v1/test-cases", json=_payload())
    assert created.status_code == 201
    tc_id = created.json()["id"]

    response = await client.delete(f"/api/v1/test-cases/{tc_id}")
    assert response.status_code == 409
