"""LangChain + GitHub Copilot chat backend with host file tools."""

from __future__ import annotations

import asyncio
from typing import Any

from ..config import resolve_github_token
from ..langchain_tool_loop import run_langchain_tool_loop
from .base import BackendCapabilities, BackendContext, QueryResult

_LC_IMPORT_ERROR: str | None = None
try:
    from langchain_githubcopilot_chat import ChatGithubCopilot

    _LC_AVAILABLE = True
except ImportError as exc:
    _LC_AVAILABLE = False
    _LC_IMPORT_ERROR = str(exc)
    ChatGithubCopilot = None  # type: ignore[misc, assignment]


class LangChainCopilotBackend:
    id = "langchain_copilot"
    display_name = "LangChain GitHub Copilot"

    def __init__(self) -> None:
        self._llm: Any = None
        self._histories: dict[str, list[dict[str, Any]]] = {}

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_host_file_tools=True,
            needs_github_token=True,
        )

    def _session_id(self, ctx: BackendContext) -> str:
        return ctx.active_session_id or "lc-local-1"

    def _allow_write(self, ctx: BackendContext) -> bool:
        if ctx.mode == "ask":
            return False
        return ctx.effective_full_access

    def _model(self, ctx: BackendContext) -> str:
        m = (ctx.config.copilot_model or "").strip()
        if m:
            return m
        return (ctx.config.model or "gpt-4o").strip() or "gpt-4o"

    def _build_llm(self, ctx: BackendContext) -> Any:
        if not _LC_AVAILABLE:
            raise RuntimeError(
                "langchain-githubcopilot-chat is not installed. Install with: "
                "pip install 'claude-cli-agent[langchain-copilot]'"
                + (f" ({_LC_IMPORT_ERROR})" if _LC_IMPORT_ERROR else "")
            )
        token = resolve_github_token(ctx.config, cwd=ctx.cwd)
        if not token:
            raise RuntimeError(
                "No GitHub/Copilot token. Set GITHUB_TOKEN or /apikey github set <token>."
            )
        kwargs: dict[str, Any] = {"model": self._model(ctx)}
        try:
            return ChatGithubCopilot(**kwargs, token=token)
        except TypeError:
            try:
                return ChatGithubCopilot(**kwargs, github_token=token)
            except TypeError:
                import os

                os.environ.setdefault("GITHUB_TOKEN", token)
                return ChatGithubCopilot(**kwargs)

    async def connect(self, ctx: BackendContext) -> None:
        self._llm = self._build_llm(ctx)
        sid = self._session_id(ctx)
        if not ctx.active_session_id:
            ctx.set_active_session_id(sid)
        self._histories.setdefault(sid, [])

    async def disconnect(self) -> None:
        self._llm = None

    async def query(self, prompt: str, ctx: BackendContext) -> QueryResult:
        if self._llm is None:
            await self.connect(ctx)
        session_id = self._session_id(ctx)
        history = self._histories.setdefault(session_id, [])

        allow_write = self._allow_write(ctx)
        system_lines = [
            "You are cagent using LangChain with GitHub Copilot models.",
            f"Workspace root: {ctx.cwd.resolve()}",
            "Use read_file, write_file, and delete_path for workspace I/O when enabled.",
        ]
        if not allow_write:
            system_lines.append("Mutating tools are disabled (ask mode or no full access).")
        system = "\n".join(system_lines)

        def _run() -> tuple[str, int, int, str | None, bool]:
            return run_langchain_tool_loop(
                self._llm,
                system=system,
                messages=history,
                cwd=ctx.cwd,
                allow_write=allow_write,
            )

        try:
            text, input_tokens, output_tokens, err, changed_files = await asyncio.to_thread(_run)
        except Exception as exc:
            err = str(exc)
            text = f"LangChain Copilot backend request failed: {err}"
            history.append({"role": "assistant", "content": text})
            ctx.persist_state()
            return QueryResult(
                text=text,
                success=False,
                error=err,
                panel_title="Assistant (LangChain Copilot)",
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
            approx_tokens=True,
            panel_title="Assistant (LangChain Copilot)",
        )

    async def authcheck(self, ctx: BackendContext) -> None:
        token = resolve_github_token(ctx.config, cwd=ctx.cwd)
        if not token:
            ctx.console.print("[red]No GitHub token for LangChain Copilot backend.[/red]")
            return
        if not _LC_AVAILABLE:
            ctx.console.print("[red]langchain-githubcopilot-chat is not installed.[/red]")
            return
        try:
            from langchain_githubcopilot_chat import get_available_models

            models = get_available_models(token=token)
            ctx.console.print(f"[green]Token OK.[/green] {len(models)} models available.")
        except Exception:
            try:
                await self.connect(ctx)
                result = await self.query("Reply with OK only.", ctx)
                if result.success:
                    ctx.console.print("[green]LangChain Copilot backend reachable.[/green]")
                else:
                    ctx.console.print(f"[yellow]Probe failed: {result.error}[/yellow]")
            except Exception as exc:
                ctx.console.print(f"[red]LangChain Copilot auth failed:[/red] {exc}")

    async def show_context(self, ctx: BackendContext) -> None:
        sid = self._session_id(ctx)
        turns = len(self._histories.get(sid, []))
        ctx.console.print(f"[bold]LangChain Copilot context:[/bold] session={sid} turns={turns}")

    async def vision_query(self, *, image_path: str, question: str, ctx: BackendContext) -> str:
        return "Vision is not supported on langchain_copilot backend yet."
