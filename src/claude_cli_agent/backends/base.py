"""Backend protocol and shared types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from rich.console import Console

from ..config import AgentConfig
from ..options_build import AgentMode


@dataclass(frozen=True)
class BackendCapabilities:
    supports_mcp: bool = False
    supports_host_file_tools: bool = False
    supports_vision: bool = False
    needs_anthropic_key: bool = False
    needs_github_token: bool = False
    supports_streaming: bool = False
    uses_claude_project_permissions: bool = False


@dataclass
class BackendContext:
    """Runtime context passed to backends on connect/query."""

    config: AgentConfig
    cwd: Path
    mode: AgentMode
    console: Console
    active_session_id: str | None
    known_session_ids: list[str]
    agents: dict[str, Any]
    effective_full_access: bool
    # Callbacks into Runtime (session state)
    set_active_session_id: Any
    add_known_session_id: Any
    persist_state: Any


@dataclass
class QueryResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error: str | None = None
    changed_files: bool = False
    approx_tokens: bool = False
    panel_title: str = "Assistant"
    response_chars: int = 0
    stream_messages: list[Any] = field(default_factory=list)


@runtime_checkable
class AgentBackend(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    def capabilities(self) -> BackendCapabilities: ...

    async def connect(self, ctx: BackendContext) -> None: ...

    async def disconnect(self) -> None: ...

    async def query(self, prompt: str, ctx: BackendContext) -> QueryResult: ...

    async def authcheck(self, ctx: BackendContext) -> None: ...

    async def show_context(self, ctx: BackendContext) -> None: ...

    async def vision_query(self, *, image_path: str, question: str, ctx: BackendContext) -> str: ...
