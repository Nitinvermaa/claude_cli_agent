"""Minimal Textual TUI launcher."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Label, LoadingIndicator


class CagentTextualApp(App[None]):
    """Lightweight full-screen dashboard with animated loading indicator."""

    TITLE = "cagent"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("cagent Textual dashboard")
            yield LoadingIndicator()
            yield Label("Press q to quit")
        yield Footer()

