
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.turbo import TurboTestStats

@pytest.mark.asyncio
async def test_turbo_full_flow(client: AsyncClient):
    # Mock the singleton turbo_engine in the endpoints module
    with patch("app.api.v1.endpoints.turbo.turbo_engine") as mock_engine:
        # Setup mocks
        mock_engine.run_test = AsyncMock(return_value="test_mock_123")
        
        mock_stats = TurboTestStats(
            test_id="test_mock_123",
            state="running",
            users=10,
            total_requests=100,
            total_failures=0,
            current_rps=50.0,
            fail_ratio=0.0,
            avg_response_time=20.0,
            p95_response_time=50.0
        )
        mock_engine.get_stats.return_value = mock_stats
        
        # 1. Start Test
        payload = {
            "target_host": "https://example.com",
            "users": 10,
            "spawn_rate": 2,
            "run_time": "10s",
            "api_ir_chain": [
                {"method": "GET", "url": "/test", "weight": 1}
            ]
        }
        
        response = await client.post("/api/v1/turbo/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["test_id"] == "test_mock_123"
        assert data["status"] == "started"
        
        # Verify run_test called
        mock_engine.run_test.assert_awaited_once()
        
        # 2. Get Stats
        response = await client.get("/api/v1/turbo/stats/test_mock_123")
        assert response.status_code == 200
        stats = response.json()
        assert stats["test_id"] == "test_mock_123"
        assert stats["users"] == 10
        
        # 3. Stop Test
        response = await client.post("/api/v1/turbo/stop/test_mock_123")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
        
        mock_engine.stop_test.assert_called_with("test_mock_123")
