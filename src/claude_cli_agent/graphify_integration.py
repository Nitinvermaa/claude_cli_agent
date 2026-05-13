"""Graphify integration helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console


class GraphifyManager:
    """Best-effort graphify orchestration to keep context fresh."""

    def __init__(self, console: Console, graphify_cmd: str = "graphify", enabled: bool = True) -> None:
        self.console = console
        self.graphify_cmd = graphify_cmd
        self.enabled = enabled
        self._missing_notified = False

    def _handle_missing_binary(self) -> None:
        self.enabled = False
        if self._missing_notified:
            return
        self._missing_notified = True
        self.console.print(
            "[yellow]graphify command not found; graphify features disabled for this session.[/yellow]"
        )

    async def maybe_update(self, cwd: Path, changed: bool) -> None:
        if not self.enabled or not changed:
            return

        self.console.print("[dim]Updating graphify context (AST-only) ...[/dim]")
        try:
            proc = await asyncio.create_subprocess_exec(
                self.graphify_cmd,
                "update",
                ".",
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            self._handle_missing_binary()
            return
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=45)
        except asyncio.TimeoutError:
            proc.kill()
            self.console.print("[yellow]graphify update timed out; continuing session.[/yellow]")
            return

        if proc.returncode == 0:
            self.console.print("[green]graphify context updated.[/green]")
        else:
            out = (stderr or stdout or b"").decode("utf-8", errors="ignore").strip()
            self.console.print(f"[yellow]graphify update failed:[/yellow] {out or 'unknown error'}")

    async def query_context(self, cwd: Path, question: str, budget: int = 700) -> str | None:
        """Fetch concise graph context before main model query."""
        if not self.enabled:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                self.graphify_cmd,
                "query",
                question,
                "--budget",
                str(budget),
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            self._handle_missing_binary()
            return None
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
        except asyncio.TimeoutError:
            proc.kill()
            return None
        if proc.returncode != 0:
            return None
        text = stdout.decode("utf-8", errors="ignore").strip()
        if not text:
            return None
        if len(text) > 2600:
            text = text[:2600] + "\n... (truncated graph context)"
        return text

    @staticmethod
    def suggest_cost_optimizations() -> list[str]:
        return [
            "Run `graphify update .` frequently and ask architecture questions against GRAPH_REPORT.md first.",
            "Use Ask/Plan modes for discovery before Agent mode to reduce expensive write loops.",
            "Set tighter `max_turns` for one-off tasks and prefer focused prompts with explicit file scopes.",
            "Use session reuse for related tasks to avoid re-reading the same context repeatedly.",
            "Defer heavy web searches unless graph context and repo context are insufficient.",
        ]
