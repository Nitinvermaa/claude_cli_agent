"""Claude Agent SDK (claude_code) backend."""

from __future__ import annotations

import uuid
from typing import Any

from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, ToolUseBlock

from ..options_build import build_options
from ..project_permissions import sync_claude_project_permissions
from ..render import render_context_usage, render_message
from .base import BackendCapabilities, BackendContext, QueryResult


class ClaudeCodeBackend:
    id = "claude_code"
    display_name = "Claude Code SDK"

    def __init__(self) -> None:
        self._client: ClaudeSDKClient | None = None
        self._ctx: BackendContext | None = None

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_mcp=True,
            supports_streaming=True,
            needs_anthropic_key=True,
            uses_claude_project_permissions=True,
        )

    @property
    def client(self) -> ClaudeSDKClient | None:
        return self._client

    async def connect(self, ctx: BackendContext) -> None:
        self._ctx = ctx
        if self._client:
            await self._client.disconnect()
            self._client = None

        if ctx.effective_full_access:
            sync_claude_project_permissions(ctx.console, ctx.cwd, full_access=True)

        resume_session_id: str | None = None
        if ctx.active_session_id:
            try:
                uuid.UUID(ctx.active_session_id)
                resume_session_id = ctx.active_session_id
            except ValueError:
                resume_session_id = None

        options = build_options(
            config=ctx.config,
            cwd=ctx.cwd,
            mode=ctx.mode,
            resume_session_id=resume_session_id,
            agents=ctx.agents,
            full_access_override=ctx.effective_full_access,
        )
        self._client = ClaudeSDKClient(options=options)
        try:
            await self._client.connect()
        except Exception:
            if resume_session_id is None:
                raise
            ctx.console.print(
                "[yellow]Previous Claude session could not be resumed; starting a fresh session.[/yellow]"
            )
            await self._client.disconnect()
            self._client = None
            ctx.set_active_session_id(None)
            options = build_options(
                config=ctx.config,
                cwd=ctx.cwd,
                mode=ctx.mode,
                resume_session_id=None,
                agents=ctx.agents,
                full_access_override=ctx.effective_full_access,
            )
            self._client = ClaudeSDKClient(options=options)
            await self._client.connect()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def query(self, prompt: str, ctx: BackendContext) -> QueryResult:
        assert self._client is not None
        response_chars = 0
        changed_files = False
        stream_messages: list[Any] = []

        await self._client.query(prompt)
        async for message in self._client.receive_response():
            stream_messages.append(message)
            render_message(ctx.console, message)
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    maybe_text = getattr(block, "text", None)
                    if isinstance(maybe_text, str):
                        response_chars += len(maybe_text)
                    if isinstance(block, ToolUseBlock) and block.name in {
                        "Write",
                        "Edit",
                        "MultiEdit",
                        "NotebookEdit",
                    }:
                        changed_files = True
            if isinstance(message, ResultMessage):
                if message.session_id:
                    ctx.add_known_session_id(message.session_id)
                    ctx.set_active_session_id(message.session_id)
                    ctx.persist_state()

        input_tokens = len(prompt) // 4
        output_tokens = max(1, response_chars // 4) if response_chars else 0
        return QueryResult(
            text="",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=True,
            changed_files=changed_files,
            approx_tokens=True,
            panel_title="",
            response_chars=response_chars,
            stream_messages=stream_messages,
        )

    async def authcheck(self, ctx: BackendContext) -> None:
        if self._client is None:
            await self.connect(ctx)
        assert self._client is not None
        probe_prompt = (
            "Auth probe: reply with exactly 'AUTH_PROBE_OK'. "
            "No tool use. No extra words."
        )
        ok = False
        await self._client.query(probe_prompt)
        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text") and getattr(block, "text", "").strip() == "AUTH_PROBE_OK":
                        ok = True
            if isinstance(message, ResultMessage):
                break
        if ok:
            ctx.console.print("[green]Auth probe succeeded.[/green]")
        else:
            ctx.console.print(
                "[yellow]Auth probe returned unexpected content, but backend is reachable.[/yellow]"
            )
        ctx.console.print(
            "[bold]Important:[/bold] claude_code backend runs through local `claude` transport. "
            "Final billing account depends on Claude Code auth precedence."
        )

    async def show_context(self, ctx: BackendContext) -> None:
        if self._client is None:
            await self.connect(ctx)
        assert self._client is not None
        usage = await self._client.get_context_usage()
        render_context_usage(ctx.console, usage)

    async def vision_query(self, *, image_path: str, question: str, ctx: BackendContext) -> str:
        return (
            "Vision via claude_code: use a prompt that references the image path; "
            "the host will forward to the SDK session."
        )
