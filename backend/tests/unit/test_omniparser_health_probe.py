import asyncio

import pytest

from app.services import omniparser_health as probe


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeClient:
    def __init__(self, status_code: int, delay_seconds: float = 0.0):
        self._status_code = status_code
        self._delay_seconds = delay_seconds

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        if self._delay_seconds > 0:
            await asyncio.sleep(self._delay_seconds)
        return _Response(self._status_code)


def test_build_omniparser_health_url_normalizes_localhost():
    url = probe.build_omniparser_health_url("http://localhost:7861")
    assert url == "http://127.0.0.1:7861/health"


@pytest.mark.asyncio
async def test_probe_returns_ok_on_200(monkeypatch):
    monkeypatch.setattr(
        probe.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(status_code=200),
    )
    status = await probe.probe_omniparser_health("http://127.0.0.1:7861")
    assert status == "ok"


@pytest.mark.asyncio
async def test_probe_returns_loading_on_non_200(monkeypatch):
    monkeypatch.setattr(
        probe.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(status_code=503),
    )
    status = await probe.probe_omniparser_health("http://127.0.0.1:7861")
    assert status == "loading"


@pytest.mark.asyncio
async def test_probe_timeout_boundary_returns_down(monkeypatch):
    monkeypatch.setattr(
        probe.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(status_code=200, delay_seconds=0.08),
    )
    status = await probe.probe_omniparser_health(
        "http://127.0.0.1:7861",
        total_timeout=0.03,
        connect_timeout=0.02,
        read_timeout=0.05,
    )
    assert status == "down"
