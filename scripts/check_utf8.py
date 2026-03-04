#!/usr/bin/env python3
"""Fail if tracked text files contain invalid UTF-8 or null bytes."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECK_DIRS = [
    ROOT / "backend" / "app" / "api" / "v1" / "endpoints",
    ROOT / "frontend" / "src" / "app",
    ROOT / "docs",
]
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".db", ".lock", ".pyc"}


def should_check(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() in SKIP_EXT:
        return False
    return True


def main() -> int:
    bad: list[str] = []
    for directory in CHECK_DIRS:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not should_check(path):
                continue
            data = path.read_bytes()
            if b"\x00" in data:
                bad.append(f"{path}: contains null bytes")
                continue
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                bad.append(f"{path}: invalid UTF-8 ({exc})")

    if bad:
        print("UTF-8 check failed:")
        for item in bad:
            print(f"- {item}")
        return 1

    print("UTF-8 check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
