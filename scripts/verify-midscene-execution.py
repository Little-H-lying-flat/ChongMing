#!/usr/bin/env python3
"""Verify ChongMing -> Midscene execution path."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

TERMINAL_STATUSES = {"passed", "failed", "error", "cancelled", "completed"}


def request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    data = None
    headers = {"accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {url} failed with HTTP {error.code}: {body}") from error


def check_png(url: str, timeout: float = 30.0) -> int:
    req = urllib.request.Request(url, headers={"accept": "image/png"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            body = response.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GET {url} failed with HTTP {error.code}: {body}") from error

    if response.status != 200:
        raise RuntimeError(f"GET {url} returned HTTP {response.status}")
    if "image/png" not in content_type.lower():
        raise RuntimeError(f"GET {url} returned content-type {content_type!r}, expected image/png")
    if not body.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"GET {url} did not return a PNG payload")
    return len(body)


def build_payload(url: str) -> dict[str, Any]:
    return {
        "tc_ids": ["VC_MIDSCENE_VERIFY_001"],
        "mode": "normal",
        "engine": "midscene",
        "parallel": False,
        "max_workers": 1,
        "dynamic_payload": [
            {
                "id": "VC_MIDSCENE_VERIFY_001",
                "name": "Midscene verification",
                "description": "Verify Midscene execution and screenshot persistence",
                "mode": "UI",
                "steps": [
                    {
                        "step_type": "UI",
                        "action_type": "goto",
                        "description": "Open verification page",
                        "target": "verification page",
                        "value": url,
                        "url": url,
                        "params": {},
                    },
                    {
                        "step_type": "UI",
                        "action_type": "assert",
                        "description": "Assert Example Domain is visible",
                        "target": "页面",
                        "value": "Example Domain",
                        "params": {},
                    },
                ],
            }
        ],
    }


def iter_screenshot_urls(api_base: str, steps_payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for case in steps_payload.get("cases") or []:
        for step in case.get("steps") or []:
            details = step.get("details") if isinstance(step.get("details"), dict) else {}
            for field in ("screenshot_before", "screenshot_after"):
                value = details.get(field)
                if isinstance(value, str) and value:
                    if value.startswith("http://") or value.startswith("https://"):
                        urls.append(value)
                    elif value.startswith("/"):
                        urls.append(f"{api_base.rstrip('/')}{value}")
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify /executions -> Midscene -> screenshots flow")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend origin without /api/v1")
    parser.add_argument("--url", default="https://example.com", help="Page URL for the smoke case")
    parser.add_argument("--timeout", type=float, default=240.0, help="Overall polling timeout in seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    api_v1 = f"{api_base}/api/v1"

    created = request_json(f"{api_v1}/executions", method="POST", payload=build_payload(args.url), timeout=120.0)
    execution_id = created.get("execution_id")
    if not execution_id:
        raise RuntimeError(f"Execution response did not include execution_id: {created}")

    print(f"execution_id={execution_id}")

    deadline = time.time() + args.timeout
    result: dict[str, Any] = {}
    while time.time() < deadline:
        result = request_json(f"{api_v1}/executions/{execution_id}/result", timeout=30.0)
        status = str(result.get("status") or "").lower()
        print(f"status={status or 'unknown'}")
        if status in TERMINAL_STATUSES:
            break
        time.sleep(args.interval)
    else:
        raise TimeoutError(f"Execution {execution_id} did not finish within {args.timeout}s")

    if str(result.get("status") or "").lower() != "passed":
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2)[:2000])

    steps_payload = request_json(f"{api_v1}/executions/{execution_id}/steps", timeout=30.0)
    screenshot_urls = iter_screenshot_urls(api_base, steps_payload)
    if not screenshot_urls:
        raise RuntimeError("No screenshot URLs found in /steps response")

    checked = []
    for url in screenshot_urls:
        checked.append({"url": url, "bytes": check_png(url)})

    print(json.dumps({
        "execution_id": execution_id,
        "status": result.get("status"),
        "summary": result.get("summary"),
        "screenshot_count": len(checked),
        "screenshots": checked,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
