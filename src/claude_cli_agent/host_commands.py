"""Host command names, help text, and completion metadata (Claude Code–style /commands)."""

from __future__ import annotations

import re

# command -> one-line description (shown in /help and completion meta)
COMMAND_META: dict[str, str] = {
    "/shortcuts": "Show keyboard and command cheat sheet (same as typing ?).",
    "/help": "List all host commands with short descriptions.",
    "/quit": "Exit cagent and disconnect backends.",
    "/mode": "Switch runtime mode: agent | plan | ask | debug.",
    "/session": "List, start, or switch Claude/SDK session id.",
    "/chat": "Named conversations: list | new <name> | switch <name>.",
    "/bwt": "Switch named conversation (alias for /chat switch).",
    "/btw": "Ask a quick side question without changing the main conversation.",
    "/context": "Show context usage / token pressure hints.",
    "/backend": "Show/switch backend. Use /backend status, /backend switch independent, or /backend independent.",
    "/subagent": "List, add, or run configured subagent profiles.",
    "/mcp": "MCP server status / reconnect / toggle (claude_code only).",
    "/vision": "Ask about an image path (vision-capable models).",
    "/approve": "Show or grant session/task full-access overrides.",
    "/approvals": "Show recent approval audit events.",
    "/annotations": "Help for @ references; type @ then Tab for file/dir paths from CWD.",
    "/pick": "Interactive fuzzy picker for annotation targets.",
    "/authcheck": "Probe auth / backend connectivity.",
    "/usage": "Print usage table and refresh HTML dashboard path.",
    "/apikey": "Show or set Anthropic API key for this install.",
    "/theme": "Theme controls: /theme show · /theme set prompt green · /theme preset readable|dark|terminal-dark|light|auto",
}

HOST_COMMANDS: tuple[str, ...] = tuple(sorted(COMMAND_META.keys()))


try:
    from prompt_toolkit.completion import Completer, Completion
except Exception:  # pragma: no cover
    Completer = object  # type: ignore[misc, assignment]
    Completion = None  # type: ignore[assignment]


class HostCommandCompleter(Completer):
    """Claude Code–style completions: `/` commands with display_meta descriptions."""

    def __init__(self, meta: dict[str, str]) -> None:
        self._meta = meta

    def get_completions(self, document, complete_event):  # type: ignore[no-untyped-def]
        if Completion is None:
            return
        line = document.text_before_cursor
        m = re.search(r"[/\\][^\s]*$", line)
        if not m:
            return
        fragment = m.group(0)
        norm = fragment.replace("\\", "/")
        if not norm.startswith("/"):
            norm = "/" + norm.lstrip("/")
        start_position = -len(fragment)
        for cmd in sorted(self._meta.keys()):
            if cmd.startswith(norm):
                yield Completion(
                    cmd,
                    start_position=start_position,
                    display_meta=self._meta.get(cmd, ""),
                )
