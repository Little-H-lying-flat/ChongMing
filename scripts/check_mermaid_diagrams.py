#!/usr/bin/env python3
"""Lightweight Mermaid validator for docs/diagrams/*.mmd."""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DIAGRAM_DIR = ROOT / "docs" / "diagrams"

ALLOWED_HEADERS = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "gitGraph",
    "mindmap",
    "timeline",
    "quadrantChart",
    "requirementDiagram",
    "xychart-beta",
    "packet-beta",
    "block-beta",
    "architecture-beta",
)

SEQUENCE_OPEN_RE = re.compile(r"^\s*(alt|opt|loop|par|critical|break|rect)\b")
SEQUENCE_END_RE = re.compile(r"^\s*end\b")
SEQUENCE_ARROW_RE = re.compile(r"(--?>>|->>|--x|->x|--\)|-\))")

SUBGRAPH_OPEN_RE = re.compile(r"^\s*subgraph\b")
SUBGRAPH_END_RE = re.compile(r"^\s*end\s*$")
FLOW_EDGE_RE = re.compile(r"(-->|==>|-.->|---)")


def _first_content_line(lines: list[str]) -> tuple[int, str] | None:
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        return idx, stripped
    return None


def _check_brackets(lines: list[str], file_path: Path) -> list[str]:
    issues: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = set(pairs.values())
    stack: list[tuple[str, int, int]] = []
    in_single = False
    in_double = False

    for line_no, line in enumerate(lines, start=1):
        escaped = False
        for col_no, ch in enumerate(line, start=1):
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == "'" and not in_double:
                in_single = not in_single
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
                continue
            if in_single or in_double:
                continue

            if ch in opens:
                stack.append((ch, line_no, col_no))
            elif ch in pairs:
                if not stack or stack[-1][0] != pairs[ch]:
                    issues.append(
                        f"{file_path}:{line_no}:{col_no}: unbalanced bracket '{ch}'"
                    )
                else:
                    stack.pop()

    for open_char, line_no, col_no in stack:
        issues.append(
            f"{file_path}:{line_no}:{col_no}: unclosed bracket '{open_char}'"
        )
    return issues


def _validate_sequence(lines: list[str], file_path: Path) -> list[str]:
    issues: list[str] = []
    block_depth = 0
    has_arrow = False

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if SEQUENCE_ARROW_RE.search(stripped):
            has_arrow = True
        if SEQUENCE_OPEN_RE.match(stripped):
            block_depth += 1
        elif SEQUENCE_END_RE.match(stripped):
            block_depth -= 1
            if block_depth < 0:
                issues.append(f"{file_path}:{line_no}: unexpected 'end'")
                block_depth = 0

    if block_depth != 0:
        issues.append(f"{file_path}: sequence block depth mismatch (missing 'end')")
    if not has_arrow:
        issues.append(f"{file_path}: sequence diagram has no message arrows")
    return issues


def _validate_flow_like(lines: list[str], file_path: Path) -> list[str]:
    issues: list[str] = []
    subgraph_depth = 0
    has_edge = False

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if FLOW_EDGE_RE.search(stripped):
            has_edge = True
        if SUBGRAPH_OPEN_RE.match(stripped):
            subgraph_depth += 1
        elif SUBGRAPH_END_RE.match(stripped):
            subgraph_depth -= 1
            if subgraph_depth < 0:
                issues.append(f"{file_path}:{line_no}: unexpected 'end'")
                subgraph_depth = 0

    if subgraph_depth != 0:
        issues.append(f"{file_path}: subgraph depth mismatch (missing 'end')")
    if not has_edge:
        issues.append(f"{file_path}: flowchart/graph has no edges")
    return issues


def _validate_file(file_path: Path) -> list[str]:
    issues: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{file_path}: invalid UTF-8 ({exc})"]

    lines = text.splitlines()
    first = _first_content_line(lines)
    if first is None:
        return [f"{file_path}: file is empty"]

    first_no, header = first
    if "\t" in text:
        issues.append(f"{file_path}: contains tab character(s), use spaces only")

    if not any(header.startswith(prefix) for prefix in ALLOWED_HEADERS):
        issues.append(
            f"{file_path}:{first_no}: unsupported Mermaid header '{header}'"
        )

    issues.extend(_check_brackets(lines, file_path))

    if header.startswith("sequenceDiagram"):
        issues.extend(_validate_sequence(lines, file_path))
    elif header.startswith("flowchart") or header.startswith("graph"):
        issues.extend(_validate_flow_like(lines, file_path))

    return issues


def main() -> int:
    files = sorted(DIAGRAM_DIR.glob("*.mmd"))
    if not files:
        print(f"No Mermaid files found in {DIAGRAM_DIR}")
        return 1

    issues: list[str] = []
    for file_path in files:
        issues.extend(_validate_file(file_path))

    if issues:
        print("Mermaid validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(f"Mermaid validation passed ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
