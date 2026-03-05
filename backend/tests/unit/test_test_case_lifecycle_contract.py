from __future__ import annotations

import pytest

from app.api.v1.endpoints.test_cases import TCIRResponse
from app.models.test_case import TCStatus


TARGET_STATES = {"draft", "review", "active", "frozen", "disabled", "archived"}

ALLOWED_TRANSITIONS = {
    "draft": {"review", "archived"},
    "review": {"draft", "active", "archived"},
    "active": {"frozen", "disabled", "archived"},
    "frozen": {"active", "disabled", "archived"},
    "disabled": {"review", "archived"},
    "archived": set(),
}


def _runtime_states() -> set[str]:
    return {member.value for member in TCStatus}


def test_runtime_model_should_match_target_6_state_set() -> None:
    assert _runtime_states() == TARGET_STATES


@pytest.mark.parametrize(
    "src,dst,expected",
    [
        ("draft", "review", True),
        ("review", "active", True),
        ("active", "frozen", True),
        ("frozen", "active", True),
        ("disabled", "review", True),
        ("archived", "active", False),
        ("draft", "active", False),
    ],
)
def test_transition_matrix_is_frozen(src: str, dst: str, expected: bool) -> None:
    assert (dst in ALLOWED_TRANSITIONS[src]) is expected


def test_legacy_response_fields_remain_stable() -> None:
    payload = {
        "id": "TC-LEGACY-001",
        "name": "legacy",
        "description": "legacy payload",
        "mode": "UI",
        "priority": "P1",
        "status": "draft",
        "steps": [{"action": "open"}],
        "tags": ["smoke"],
        "created_at": "2026-03-04T00:00:00",
        "updated_at": "2026-03-04T00:00:00",
    }
    model = TCIRResponse(**payload)
    data = model.model_dump()

    for field in (
        "id",
        "name",
        "description",
        "mode",
        "priority",
        "status",
        "steps",
        "tags",
        "created_at",
        "updated_at",
    ):
        assert field in data


def test_future_optional_fields_are_accepted_without_breaking_legacy() -> None:
    payload = {
        "id": "TC-NEXT-001",
        "name": "next",
        "description": "future",
        "mode": "UI",
        "priority": "P1",
        "status": "review",
        "steps": [],
        "tags": [],
        "created_at": "2026-03-04T00:00:00",
        "updated_at": "2026-03-04T00:00:00",
        "lifecycle_state": "review",
        "last_execution_summary": {"pass_rate": 1.0},
    }
    TCIRResponse(**payload)
