from contextvars import ContextVar, Token
from typing import Any, Callable, Dict, Optional


ProgressReporter = Callable[[str, int, Optional[Dict[str, Any]]], None]
_progress_reporter: ContextVar[Optional[ProgressReporter]] = ContextVar(
    "neural_design_progress_reporter",
    default=None,
)


def set_progress_reporter(reporter: Optional[ProgressReporter]) -> Token:
    return _progress_reporter.set(reporter)


def reset_progress_reporter(token: Token) -> None:
    _progress_reporter.reset(token)


def report_progress(stage: str, progress: int, extra: Optional[Dict[str, Any]] = None) -> None:
    reporter = _progress_reporter.get()
    if not reporter:
        return
    reporter(stage, progress, extra or {})
