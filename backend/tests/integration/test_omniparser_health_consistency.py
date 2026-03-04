from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.endpoints import dashboard as dashboard_endpoint
from app.api.v1.endpoints import health as health_endpoint


def _reset_health_cache() -> None:
    health_endpoint._health_cache["data"] = None
    health_endpoint._health_cache["ts"] = 0


@pytest.mark.asyncio
async def test_health_and_dashboard_are_consistent_when_omniparser_ok(client):
    _reset_health_cache()
    with patch(
        "app.api.v1.endpoints.health.probe_omniparser_health",
        AsyncMock(return_value="ok"),
    ), patch(
        "app.api.v1.endpoints.dashboard.probe_omniparser_health",
        AsyncMock(return_value="ok"),
    ):
        health_resp = await client.get("/api/v1/health")
        dashboard_resp = await client.get("/api/v1/dashboard/overview")

    assert health_resp.status_code == 200
    assert dashboard_resp.status_code == 200
    assert health_resp.json()["services"]["omniparser"] == "ok"
    assert dashboard_resp.json()["kpis"]["omniparser_status"] == dashboard_endpoint.STATUS_OK


@pytest.mark.asyncio
async def test_health_and_dashboard_are_consistent_when_omniparser_down(client):
    _reset_health_cache()
    with patch(
        "app.api.v1.endpoints.health.probe_omniparser_health",
        AsyncMock(return_value="down"),
    ), patch(
        "app.api.v1.endpoints.dashboard.probe_omniparser_health",
        AsyncMock(return_value="down"),
    ):
        health_resp = await client.get("/api/v1/health")
        dashboard_resp = await client.get("/api/v1/dashboard/overview")

    assert health_resp.status_code == 200
    assert dashboard_resp.status_code == 200
    assert health_resp.json()["services"]["omniparser"] == "down"
    assert dashboard_resp.json()["kpis"]["omniparser_status"] == dashboard_endpoint.STATUS_ERR
