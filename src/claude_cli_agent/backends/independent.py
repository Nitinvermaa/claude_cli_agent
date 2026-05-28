"""Direct Anthropic API backend with host file tools."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

import anthropic

from ..independent_agent import run_independent_tool_loop
from .base import BackendCapabilities, BackendContext, QueryResult


class IndependentBackend:
    id = "independent"
    display_name = "Anthropic API (independent)"

    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None
        self._histories: dict[str, list[dict[str, Any]]] = {}

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_host_file_tools=True,
            supports_vision=True,
            needs_anthropic_key=True,
        )

    def _session_id(self, ctx: BackendContext) -> str:
        return ctx.active_session_id or "local-1"

    def _allow_write(self, ctx: BackendContext) -> bool:
        if ctx.mode == "ask":
            return False
        return ctx.effective_full_access

    async def connect(self, ctx: BackendContext) -> None:
        key = (ctx.config.api_key or "").strip()
        if not key:
            raise RuntimeError(
                "No Anthropic API key configured. Set ANTHROPIC_API_KEY, use /apikey set, or run cagent config."
            )
        self._client = anthropic.Anthropic(api_key=key)
        sid = self._session_id(ctx)
        if not ctx.active_session_id:
            ctx.set_active_session_id(sid)
        self._histories.setdefault(sid, [])

    async def disconnect(self) -> None:
        self._client = None

    async def query(self, prompt: str, ctx: BackendContext) -> QueryResult:
        if self._client is None:
            await self.connect(ctx)
        assert self._client is not None
        session_id = self._session_id(ctx)
        history = self._histories.setdefault(session_id, [])
        history.append({"role": "user", "content": prompt})

        allow_write = self._allow_write(ctx)
        system_lines = [
            "You are cagent, a production coding assistant using the Anthropic API (independent backend).",
            f"Workspace root on disk: {ctx.cwd.resolve()}",
            "You always have the read_file tool to inspect project files.",
            "On large codebases: sample key modules first (entry points, configs, tests); avoid dumping "
            "every source file into context before writing the report.",
        ]
        if allow_write:
            system_lines.append(
                "You have write_file (create/overwrite) and delete_path (remove files or directories; "
                "use recursive=true only when intentionally deleting a non-empty directory tree). "
                "Use these tools for real edits under the workspace root—do not ask the user to paste into an editor "
                "unless they prefer that."
            )
        else:
            system_lines.append(
                "Mutating tools are disabled in ask mode (read-only). Use read_file only; switch to "
                "/mode agent, plan, or debug for writes, or use the claude_code backend."
            )
        system = "\n".join(system_lines)

        def _run() -> tuple[str, int, int, str | None, bool]:
            return run_independent_tool_loop(
                self._client,
                model=ctx.config.model,
                system=system,
                messages=history,
                cwd=ctx.cwd,
                allow_write=allow_write,
            )

        try:
            text, input_tokens, output_tokens, err, changed_files = await asyncio.to_thread(_run)
        except Exception as exc:
            err = str(exc)
            text = f"Independent backend request failed: {err}"
            history.append({"role": "assistant", "content": text})
            ctx.persist_state()
            return QueryResult(
                text=text,
                success=False,
                error=err,
                panel_title="Assistant (independent backend)",
            )

        success = err is None
        ctx.add_known_session_id(session_id)
        ctx.set_active_session_id(session_id)
        ctx.persist_state()
        return QueryResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
            error=err,
            changed_files=changed_files,
            panel_title="Assistant (independent backend)",
        )

    async def authcheck(self, ctx: BackendContext) -> None:
        ctx.console.print(
            "[green]Independent backend uses direct Anthropic API from cagent config key.[/green]"
        )
        ctx.console.print(
            "[dim]Workspace tools: read_file; write_file and delete_path when not in ask mode and full access is on.[/dim]"
        )

    async def show_context(self, ctx: BackendContext) -> None:
        sid = self._session_id(ctx)
        turns = len(self._histories.get(sid, []))
        approx_chars = sum(
            len(str(item.get("content", "")))
            for item in self._histories.get(sid, [])
            if isinstance(item, dict)
        )
        approx_tokens = approx_chars // 4
        ctx.console.print(
            f"[bold]Independent context:[/bold] session={sid} turns={turns} ~tokens={approx_tokens}"
        )

    async def vision_query(self, *, image_path: str, question: str, ctx: BackendContext) -> str:
        assert self._client is not None
        target = (ctx.cwd / image_path).resolve() if not Path(image_path).is_absolute() else Path(image_path)
        if not target.exists() or not target.is_file():
            return f"Image not found: {image_path}"
        mime = "image/png"
        suffix = target.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        elif suffix == ".webp":
            mime = "image/webp"
        try:
            raw = target.read_bytes()
        except OSError as exc:
            return f"Failed to read image: {exc}"
        b64 = base64.b64encode(raw).decode("utf-8")

        def _call() -> anthropic.types.Message:
            return self._client.messages.create(  # type: ignore[union-attr]
                model=ctx.config.model,
                max_tokens=1200,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": question},
                        ],
                    }
                ],
            )

        try:
            response = await asyncio.to_thread(_call)
        except Exception as exc:
            return f"Vision request failed: {exc}"
        out: list[str] = []
        for block in response.content:
            maybe_text = getattr(block, "text", None)
            if maybe_text:
                out.append(maybe_text)
        return "\n".join(out).strip() or "(no text response)"
