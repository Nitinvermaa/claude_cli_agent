"""GitHub Copilot SDK backend."""

from __future__ import annotations

from typing import Any

from ..config import apply_github_token_to_env, resolve_github_token
from .base import BackendCapabilities, BackendContext, QueryResult

_COPILOT_IMPORT_ERROR: str | None = None
try:
    from copilot import CopilotClient
    from copilot.session import PermissionHandler

    _COPILOT_AVAILABLE = True
except ImportError as exc:
    _COPILOT_AVAILABLE = False
    _COPILOT_IMPORT_ERROR = str(exc)
    CopilotClient = None  # type: ignore[misc, assignment]
    PermissionHandler = None  # type: ignore[misc, assignment]


def _permission_handler(full_access: bool, mode: str) -> Any:
    if not _COPILOT_AVAILABLE or PermissionHandler is None:
        return None
    if full_access and mode in {"agent", "debug", "plan"}:
        return PermissionHandler.approve_all
    return PermissionHandler.approve_all


class CopilotSdkBackend:
    id = "copilot_sdk"
    display_name = "GitHub Copilot SDK"

    def __init__(self) -> None:
        self._client: Any = None
        self._session: Any = None
        self._copilot_session_id: str | None = None

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_streaming=True,
            needs_github_token=True,
        )

    def _model(self, ctx: BackendContext) -> str:
        m = (ctx.config.copilot_model or "").strip()
        if m:
            return m
        return (ctx.config.model or "gpt-4.1").strip() or "gpt-4.1"

    async def connect(self, ctx: BackendContext) -> None:
        if self._session is not None and self._client is not None:
            return
        if not _COPILOT_AVAILABLE:
            raise RuntimeError(
                "GitHub Copilot SDK is not installed. Install with: "
                "pip install 'claude-cli-agent[copilot]' or pip install github-copilot-sdk"
                + (f" ({_COPILOT_IMPORT_ERROR})" if _COPILOT_IMPORT_ERROR else "")
            )
        token = resolve_github_token(ctx.config, cwd=ctx.cwd)
        if not token:
            raise RuntimeError(
                "No GitHub token for Copilot. Set GITHUB_TOKEN, GH_TOKEN, or COPILOT_GITHUB_TOKEN, "
                "or use /apikey github set <token>."
            )
        apply_github_token_to_env(token)

        if self._client is not None:
            try:
                await self._client.stop()
            except Exception:
                pass
            self._client = None
            self._session = None

        self._client = CopilotClient()
        await self._client.start()

        handler = _permission_handler(ctx.effective_full_access, ctx.mode)
        session_kw: dict[str, Any] = {"model": self._model(ctx)}
        if handler is not None:
            session_kw["on_permission_request"] = handler

        self._session = await self._client.create_session(**session_kw)
        sid = getattr(self._session, "id", None) or getattr(self._session, "session_id", None)
        if sid:
            self._copilot_session_id = str(sid)
            ctx.set_active_session_id(self._copilot_session_id)
            ctx.add_known_session_id(self._copilot_session_id)
            ctx.persist_state()

    async def disconnect(self) -> None:
        self._session = None
        if self._client is not None:
            try:
                await self._client.stop()
            except Exception:
                pass
            self._client = None

    async def query(self, prompt: str, ctx: BackendContext) -> QueryResult:
        if self._session is None:
            await self.connect(ctx)
        assert self._session is not None

        try:
            response = await self._session.send_and_wait(prompt)
        except Exception as exc:
            err = str(exc)
            return QueryResult(
                text=f"Copilot SDK request failed: {err}",
                success=False,
                error=err,
                panel_title="Assistant (Copilot SDK)",
            )

        text = ""
        data = getattr(response, "data", None)
        if data is not None:
            text = str(getattr(data, "content", "") or "")
        if not text:
            text = str(response)

        approx_in = max(1, len(prompt) // 4)
        approx_out = max(1, len(text) // 4)
        return QueryResult(
            text=text.strip() or "(no text response)",
            input_tokens=approx_in,
            output_tokens=approx_out,
            success=True,
            approx_tokens=True,
            panel_title="Assistant (Copilot SDK)",
        )

    async def authcheck(self, ctx: BackendContext) -> None:
        token = resolve_github_token(ctx.config, cwd=ctx.cwd)
        if not token:
            ctx.console.print("[red]No GitHub token configured for Copilot SDK.[/red]")
            ctx.console.print("[dim]Set GITHUB_TOKEN or /apikey github set <pat>[/dim]")
            return
        masked = f"{token[:4]}...{token[-4:]}" if len(token) > 12 else "***"
        ctx.console.print(f"[green]GitHub token configured[/green] ({masked})")
        if not _COPILOT_AVAILABLE:
            ctx.console.print("[red]github-copilot-sdk package is not installed.[/red]")
            return
        try:
            await self.connect(ctx)
            result = await self.query(
                "Auth probe: reply with exactly AUTH_PROBE_OK. No tools.",
                ctx,
            )
            if "AUTH_PROBE_OK" in result.text:
                ctx.console.print("[green]Copilot SDK auth probe succeeded.[/green]")
            else:
                ctx.console.print(
                    "[yellow]Copilot SDK reachable; probe reply did not match exactly.[/yellow]"
                )
        except Exception as exc:
            ctx.console.print(f"[red]Copilot SDK connection failed:[/red] {exc}")
        finally:
            await self.disconnect()

    async def show_context(self, ctx: BackendContext) -> None:
        sid = ctx.active_session_id or self._copilot_session_id or "(none)"
        ctx.console.print(f"[bold]Copilot SDK session:[/bold] {sid}")
        ctx.console.print(f"[dim]Model: {self._model(ctx)}[/dim]")

    async def vision_query(self, *, image_path: str, question: str, ctx: BackendContext) -> str:
        return (
            "Vision is not yet wired for copilot_sdk. "
            "Switch to independent backend or reference the image path in your prompt."
        )
