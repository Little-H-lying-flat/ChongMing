from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib
import inspect
import re
from typing import Optional


@dataclass(frozen=True)
class AutoGenRuntimeStatus:
    available: bool
    version: str
    reason: Optional[str]
    supports_register_function: bool
    supports_speaker_selection: bool
    supports_async_chat: bool


def _parse_version(version: str) -> tuple[int, ...]:
    parts = [int(token) for token in re.findall(r"\d+", version or "")]
    return tuple(parts or [0])


@lru_cache(maxsize=1)
def get_autogen_runtime_status() -> AutoGenRuntimeStatus:
    try:
        autogen = importlib.import_module("autogen")
    except Exception as exc:
        return AutoGenRuntimeStatus(
            available=False,
            version="missing",
            reason=f"autogen import failed: {exc}",
            supports_register_function=False,
            supports_speaker_selection=False,
            supports_async_chat=False,
        )

    version = str(getattr(autogen, "__version__", "unknown"))
    agentchat = getattr(autogen, "agentchat", None)
    supports_register_function = callable(getattr(agentchat, "register_function", None))

    supports_speaker_selection = False
    group_chat = getattr(autogen, "GroupChat", None)
    if group_chat is not None:
        try:
            supports_speaker_selection = (
                "speaker_selection_method" in inspect.signature(group_chat.__init__).parameters
            )
        except (TypeError, ValueError):
            supports_speaker_selection = False

    supports_async_chat = hasattr(getattr(autogen, "UserProxyAgent", object), "a_initiate_chat")

    if _parse_version(version) < (0, 2):
        try:
            completion_module = importlib.import_module("autogen.oai.completion")
        except Exception as exc:
            return AutoGenRuntimeStatus(
                available=False,
                version=version,
                reason=f"autogen {version} legacy oai backend import failed: {exc}",
                supports_register_function=supports_register_function,
                supports_speaker_selection=supports_speaker_selection,
                supports_async_chat=supports_async_chat,
            )

        completion_error = getattr(completion_module, "ERROR", None)
        if completion_error is not None:
            return AutoGenRuntimeStatus(
                available=False,
                version=version,
                reason=str(completion_error),
                supports_register_function=supports_register_function,
                supports_speaker_selection=supports_speaker_selection,
                supports_async_chat=supports_async_chat,
            )

    return AutoGenRuntimeStatus(
        available=True,
        version=version,
        reason=None,
        supports_register_function=supports_register_function,
        supports_speaker_selection=supports_speaker_selection,
        supports_async_chat=supports_async_chat,
    )


def clear_autogen_runtime_status_cache() -> None:
    get_autogen_runtime_status.cache_clear()
