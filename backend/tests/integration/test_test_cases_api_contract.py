from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution, ExecutionStatus, ExecutionStep


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
async def test_nested_only_api_case_returns_v2_shape_and_aliases(client) -> None:
    payload = {
        "name": "nested-api-case",
        "description": "nested only api case",
        "mode": "API",
        "priority": "P1",
        "steps": [
            {
                "id": "STEP_001",
                "name": "Ping",
                "step_type": "API",
                "request": {
                    "method": "GET",
                    "url": "http://example.test/ping",
                    "headers": {"X-Test": "1"},
                },
                "assertion": {
                    "status_code": 200,
                    "json_assertions": {"$.pong": True},
                },
                "extraction": {"pong": "$.pong"},
            }
        ],
        "tags": ["api", "v2"],
    }

    created = await client.post("/api/v1/test-cases", json=payload)
    assert created.status_code == 201
    tc_id = created.json()["id"]

    fetched = await client.get(f"/api/v1/test-cases/{tc_id}")
    assert fetched.status_code == 200
    step = fetched.json()["steps"][0]
    assert step["protocol"] == "API-IR"
    assert step["version"] == "2.0"
    assert step["request"]["url"] == "http://example.test/ping"
    assert step["assertion"]["status_code"] == 200
    assert step["method"] == "GET"
    assert step["url"] == "http://example.test/ping"
    assert step["expected_status_code"] == 200
    assert step["json_assertions"] == {"$.pong": True}
    assert step["extract"] == {"pong": "$.pong"}


@pytest.mark.asyncio
async def test_delete_should_block_when_referenced_by_execution(
    client,
    db_session: AsyncSession,
) -> None:
    created = await client.post("/api/v1/test-cases", json=_payload())
    assert created.status_code == 201
    tc_id = created.json()["id"]

    execution_id = "EXEC-CONTRACT-001"
    db_session.add(
        Execution(
            id=execution_id,
            config={"tc_ids": [tc_id]},
            status=ExecutionStatus.RUNNING,
            total_cases=1,
        )
    )
    db_session.add(
        ExecutionStep(
            execution_id=execution_id,
            tc_id=tc_id,
            status=ExecutionStatus.RUNNING,
            step_results={"steps": []},
        )
    )
    await db_session.commit()

    response = await client.delete(f"/api/v1/test-cases/{tc_id}")
    assert response.status_code == 409
