"""Shared OmniParser health probe utilities."""

from __future__ import annotations

import asyncio

import httpx
from loguru import logger

DEFAULT_TOTAL_TIMEOUT = 3.5
DEFAULT_CONNECT_TIMEOUT = 1.0
DEFAULT_READ_TIMEOUT = 2.5


def build_omniparser_health_url(base_url: str) -> str:
    """Build health URL and normalize localhost to avoid local DNS pitfalls."""
    normalized_base = (base_url or "").rstrip("/")
    return f"{normalized_base}/health".replace("localhost", "127.0.0.1")


async def probe_omniparser_health(
    base_url: str,
    *,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    read_timeout: float = DEFAULT_READ_TIMEOUT,
) -> str:
    """
    Probe OmniParser health endpoint.

    Returns:
    - "ok" when HTTP status is 200
    - "loading" when endpoint is reachable but non-200
    - "down" on timeout/network/other probe failure
    """
    url = build_omniparser_health_url(base_url)
    timeout = httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=read_timeout,
        pool=connect_timeout,
    )
    try:
        async with asyncio.timeout(total_timeout):
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                response = await client.get(url)
                return "ok" if response.status_code == 200 else "loading"
    except Exception as exc:
        logger.warning(f"OmniParser health probe failed: {exc}")
        return "down"
