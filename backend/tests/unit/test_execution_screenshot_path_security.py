import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.executions import (
    _ensure_safe_filename,
    _resolve_safe_screenshot_path,
)


def test_ensure_safe_filename_accepts_expected_chars():
    assert _ensure_safe_filename("TC-001_2.before.png", "tc_id") == "TC-001_2.before.png"


@pytest.mark.parametrize("value", ["../x", "..\\x", "a/b", "a:b", "", "含中文"])
def test_ensure_safe_filename_rejects_invalid(value: str):
    with pytest.raises(HTTPException) as exc:
        _ensure_safe_filename(value, "filename")
    assert exc.value.status_code == 400


def test_resolve_safe_screenshot_path_under_expected_base():
    path = _resolve_safe_screenshot_path("EXEC_ABC", "TC_1_before.png")
    assert "data" in str(path)
    assert "screenshots" in str(path)


def test_resolve_safe_screenshot_path_rejects_traversal():
    with pytest.raises(HTTPException) as exc:
        _resolve_safe_screenshot_path("EXEC_ABC", "../evil.png")
    assert exc.value.status_code == 400
