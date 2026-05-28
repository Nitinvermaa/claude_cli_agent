"""Backend registry and factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import DEFAULT_BACKEND
from .base import AgentBackend

if TYPE_CHECKING:
    pass

BACKEND_IDS = ("claude_code", "independent", "copilot_sdk", "langchain_copilot")

_BUILTIN: dict[str, type] = {}


def _register_builtins() -> None:
    if _BUILTIN:
        return
    from .claude_code import ClaudeCodeBackend
    from .independent import IndependentBackend

    _BUILTIN["claude_code"] = ClaudeCodeBackend
    _BUILTIN["independent"] = IndependentBackend


def normalize_backend_id(value: str | None) -> str:
    v = (value or DEFAULT_BACKEND).strip().lower()
    if v in BACKEND_IDS:
        return v
    return DEFAULT_BACKEND


def list_backends() -> list[str]:
    return list(BACKEND_IDS)


def ensure_backend_available(backend_id: str) -> None:
    bid = normalize_backend_id(backend_id)
    _register_builtins()
    if bid in ("copilot_sdk", "langchain_copilot"):
        if bid == "copilot_sdk":
            from . import copilot_sdk as mod

            if not mod._COPILOT_AVAILABLE:
                raise RuntimeError(
                    "Install Copilot SDK: pip install 'claude-cli-agent[copilot]' "
                    f"({mod._COPILOT_IMPORT_ERROR})"
                )
        if bid == "langchain_copilot":
            from . import langchain_copilot as mod

            if not mod._LC_AVAILABLE:
                raise RuntimeError(
                    "Install LangChain Copilot: pip install 'claude-cli-agent[langchain-copilot]' "
                    f"({mod._LC_IMPORT_ERROR})"
                )


def create_backend(backend_id: str) -> AgentBackend:
    bid = normalize_backend_id(backend_id)
    ensure_backend_available(bid)
    _register_builtins()
    if bid == "copilot_sdk":
        from .copilot_sdk import CopilotSdkBackend

        return CopilotSdkBackend()
    if bid == "langchain_copilot":
        from .langchain_copilot import LangChainCopilotBackend

        return LangChainCopilotBackend()
    cls = _BUILTIN[bid]
    return cls()  # type: ignore[return-value]


def get_backend(backend_id: str) -> AgentBackend:
    return create_backend(backend_id)
