"""Terminal rendering utilities."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from claude_agent_sdk.types import (
    AssistantMessage,
    Message,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .console_theme import cli_theme_preset, use_dark_ink

# Official Claude Code product docs (shortcuts panel footer).
CLAUDE_CODE_DOCS_URL = "https://docs.anthropic.com/en/docs/claude-code/overview"


def _panel_width(console: Console) -> int:
    w = console.width or 88
    return max(44, w - 2)


def _system_payload_preview(data: object, *, max_chars: int = 1400) -> str:
    try:
        if isinstance(data, dict):
            s = json.dumps(data, ensure_ascii=False, default=str)
        else:
            s = str(data)
    except Exception:
        s = repr(data)
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + f" … [truncated, {len(s) - max_chars} more chars]"


def render_welcome(
    console: Console,
    mode: str,
    cwd: str,
    *,
    prompt_color: str = "cyan",
    accent_color: str = "magenta",
) -> None:
    # Build with Text (literal "/") so Rich markup and old installs cannot show "\".
    from claude_cli_agent import __version__

    pc = prompt_color
    body = Text()
    if use_dark_ink():
        # Pastel / white / light-blue terminals: never rely on dim or pale cyan alone.
        ink = "#0f172a"
        version_c = "#334155"
        comma_c = "#475569"
        cmd = "bold #0369a1"
        body.append("cagent ", style=f"bold {ink}")
        body.append(f"{__version__}\n", style=version_c)
        body.append("Mode: ", style=ink)
        body.append(f"{mode}\n", style="#a16207")
        body.append("CWD: ", style=ink)
        body.append(f"{cwd}\n", style="#047857")
        body.append("Commands: ", style=ink)
        body.append("/help", style=cmd)
        body.append(", ", style=comma_c)
        body.append("/mode", style=cmd)
        body.append(" agent|plan|ask|debug, ", style=comma_c)
        body.append("/session", style=cmd)
        body.append(", ", style=comma_c)
        body.append("/context", style=cmd)
        body.append(", ", style=comma_c)
        body.append("/quit", style=cmd)
        body.append("\n")
        body.append("Also: /backend, /usage, /authcheck — full list: /help", style=comma_c)
        border = "#0e7490"
        title = "[bold #0f172a]Claude SDK Coding Agent[/bold #0f172a]"
    else:
        # Claude Code-like dark palette: cool cyan accents on near-black surfaces.
        fg = "#e5e7eb"
        muted = "#cbd5e1"
        cmd = "#22d3ee"
        body.append("cagent ", style=f"bold {cmd}")
        body.append(f"{__version__}\n", style=muted)
        body.append("Mode: ", style=fg)
        body.append(f"{mode}\n", style="#fbbf24")
        body.append("CWD: ", style=fg)
        body.append(f"{cwd}\n", style="#86efac")
        body.append("Commands: ", style=fg)
        body.append("/help", style=f"bold {cmd}")
        body.append(", ", style=muted)
        body.append("/mode", style=f"bold {cmd}")
        body.append(" agent|plan|ask|debug, ", style=fg)
        body.append("/session", style=f"bold {cmd}")
        body.append(", ", style=muted)
        body.append("/context", style=f"bold {cmd}")
        body.append(", ", style=muted)
        body.append("/quit", style=f"bold {cmd}")
        body.append("\n")
        body.append("Also: /backend, /usage, /authcheck — full list: /help", style=fg)
        border = "#d946ef" if accent_color in {"magenta", "bright_magenta"} else "#22d3ee"
        title = "[bold #22d3ee]Claude SDK Coding Agent[/bold #22d3ee]"
    console.print(
        Panel.fit(
            body,
            title=title,
            border_style=border,
        )
    )


def _shortcut_cell(
    rows: list[tuple[str, str]],
    *,
    key_style: str,
    dim_style: str,
) -> Text:
    t = Text()
    for i, (label, desc) in enumerate(rows):
        if i:
            t.append("\n")
        t.append(label, style=key_style)
        t.append(" ")
        t.append(desc, style=dim_style)
    return t


def render_shortcuts_help(console: Console) -> None:
    """Claude Code–style shortcuts sheet: version header, intro, 3-column hints, doc link."""
    from claude_cli_agent import __version__

    dark_term = not use_dark_ink()
    accent = "bright_cyan" if dark_term else "#0e7490"
    head = "bold white" if dark_term else "bold #0f172a"
    key_style = "bold bright_cyan" if dark_term else "bold #0369a1"
    dim_style = "#9ca3af" if dark_term else "#475569"
    link_style = "bright_cyan" if dark_term else "#0369a1"

    console.print(Rule(style=accent))
    console.print(Text(f"cagent {__version__}", style=head))
    console.print(Rule(style=accent))
    console.print(
        Text(
            "cagent runs the Claude Agent SDK with local approvals, @-annotations, graphify, and dual backends "
            "(claude_code or independent) — from your terminal.",
            style=dim_style,
        )
    )
    console.print()
    console.print(Text("Shortcuts", style=head))
    console.print()

    col1 = _shortcut_cell(
        [
            ("?", "shortcuts (this panel)"),
            ("/ + Tab", "host commands + hints"),
            ("/btw", "side question"),
            ("@path", "file / dir / glob (Tab)"),
        ],
        key_style=key_style,
        dim_style=dim_style,
    )
    col2 = _shortcut_cell(
        [
            ("/help", "all host commands"),
            ("/pick", "fuzzy @ targets"),
            ("/session", "SDK session id"),
            ("/chat", "named threads"),
        ],
        key_style=key_style,
        dim_style=dim_style,
    )
    col3 = _shortcut_cell(
        [
            ("Enter", "empty line = hint only"),
            ("Esc", "cancel prompts"),
            ("version", "cagent -V in shell"),
            ("CLI_THEME", "light / dark / auto"),
        ],
        key_style=key_style,
        dim_style=dim_style,
    )
    cw = console.width or 88
    col_w = max(26, (cw - 4) // 3)
    grid = Table(show_header=False, box=None, pad_edge=False, expand=True)
    grid.add_column(min_width=20, max_width=col_w, no_wrap=False)
    grid.add_column(min_width=20, max_width=col_w, no_wrap=False)
    grid.add_column(min_width=20, max_width=col_w, no_wrap=False)
    grid.add_row(col1, col2, col3)
    console.print(grid)
    console.print()
    foot = Text()
    foot.append("For more help: ", style=dim_style)
    foot.append(CLAUDE_CODE_DOCS_URL, style=link_style)
    foot.append(" · ", style=dim_style)
    foot.append("cagent: see README in this repo", style=dim_style)
    console.print(foot)


def _assistant_text_blocks(msg: AssistantMessage) -> Iterable[str]:
    for block in msg.content:
        if isinstance(block, TextBlock):
            yield block.text


_TOOL_OUTPUT_MAX_CHARS = 120_000


def _tool_result_content_to_str(content: str | list[dict[str, Any]] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
            parts.append(str(item["text"]))
        elif isinstance(item, dict):
            try:
                parts.append(json.dumps(item, ensure_ascii=False, default=str))
            except Exception:
                parts.append(repr(item))
        else:
            parts.append(str(item))
    return "\n".join(parts)


def _iter_markdown_code_fences(text: str) -> Iterable[tuple[str, str, str]]:
    """Yield ("text"|"code", payload, language)."""
    pattern = re.compile(r"```([a-zA-Z0-9_+\-]*)\n(.*?)```", re.DOTALL)
    cursor = 0
    for m in pattern.finditer(text):
        if m.start() > cursor:
            yield ("text", text[cursor : m.start()], "")
        lang = (m.group(1) or "text").strip() or "text"
        code = m.group(2).rstrip("\n")
        yield ("code", code, lang)
        cursor = m.end()
    if cursor < len(text):
        yield ("text", text[cursor:], "")


def _render_assistant_like_panel(
    console: Console,
    body_text: str,
    *,
    title: str,
    preset: str | None = None,
) -> None:
    preset = preset or cli_theme_preset()
    width = _panel_width(console)
    body = Text(body_text, overflow="fold", no_wrap=False)
    # High-contrast pop-out only on light/tinted terminals.
    # On true dark themes, keep normal dark panel text to avoid white background blocks.
    popout = use_dark_ink()
    if popout:
        body.stylize("black on bright_white", 0, len(body))
        console.print(
            Panel(
                body,
                title=f"[bold bright_cyan]{title}[/bold bright_cyan]",
                border_style="bright_cyan",
                width=width,
                padding=(0, 1),
            )
        )
    else:
        console.print(
            Panel(
                body,
                title=f"[bold cyan]{title}[/bold cyan]",
                border_style="cyan",
                width=width,
                padding=(0, 1),
            )
        )


def _render_assistant_markdown_blocks(console: Console, text: str, *, preset: str) -> None:
    width = _panel_width(console)
    title_style = "[bold bright_cyan]Assistant[/bold bright_cyan]"
    for kind, payload, lang in _iter_markdown_code_fences(text):
        if kind == "text":
            chunk = payload.strip()
            if not chunk:
                continue
            _render_assistant_like_panel(console, chunk, title="Assistant", preset=preset)
            continue
        syntax = Syntax(payload, lang or "text", word_wrap=True, line_numbers=False)
        console.print(
            Panel(
                syntax,
                title=f"{title_style} [#9ca3af]code:{lang}[/#9ca3af]",
                border_style="bright_cyan",
                width=width,
                padding=(0, 1),
            )
        )


def render_btw_reply(console: Console, answer: str) -> None:
    """Side-channel reply: same high-contrast assistant styling, distinct title."""
    _render_assistant_like_panel(console, answer, title="/btw (side channel)")


def _render_tool_output(console: Console, body: str, *, is_error: bool | None) -> None:
    raw = body.expandtabs()
    if len(raw) > _TOOL_OUTPUT_MAX_CHARS:
        over = len(raw) - _TOOL_OUTPUT_MAX_CHARS
        raw = raw[:_TOOL_OUTPUT_MAX_CHARS] + f"\n\n… [truncated, {over} more chars]"
    width = _panel_width(console)
    panel_body = Text(raw, overflow="fold", no_wrap=False)
    err = bool(is_error)
    if err:
        title = "[bold red]Tool output[/bold red]"
        border = "red"
    else:
        title = "[bold green]Tool output[/bold green]"
        border = "green"
    console.print(Panel(panel_body, title=title, border_style=border, width=width, padding=(0, 1)))


def render_message(console: Console, message: Message) -> None:
    preset = cli_theme_preset()
    ink = use_dark_ink()
    if isinstance(message, UserMessage):
        if isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    text = _tool_result_content_to_str(block.content).strip("\n")
                    if text or block.is_error:
                        _render_tool_output(console, text or "(empty)", is_error=block.is_error)
        return

    if isinstance(message, AssistantMessage):
        text = "\n".join(_assistant_text_blocks(message)).strip()
        if text:
            if "```" in text:
                _render_assistant_markdown_blocks(console, text, preset=preset)
            else:
                _render_assistant_like_panel(console, text, title="Assistant", preset=preset)
        if ink:
            tool_style = "#475569"
        else:
            tool_style = "#cbd5e1" if preset == "dark" else "dim"
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                console.print(Text(f"Tool: {block.name}", style=tool_style))
        return

    if isinstance(message, ResultMessage):
        cost = "n/a" if message.total_cost_usd is None else f"${message.total_cost_usd:.4f}"
        console.print(f"[bold green]Result[/bold green] turns={message.num_turns} cost={cost}")
        # Do not print message.result by default: SDK often echoes assistant text here,
        # which makes output look duplicated after the Assistant panel.
        return

    if isinstance(message, StreamEvent):
        event_type = message.event.get("type", "event")
        stream_style = "#64748b" if ink else ("#a3b1c6" if preset == "dark" else "dim grey42")
        console.print(Text(f"stream: {event_type}", style=stream_style))
        return

    if isinstance(message, SystemMessage):
        preview = _system_payload_preview(message.data)
        sys_style = "#64748b" if ink else ("#a3b1c6" if preset == "dark" else "dim grey42")
        console.print(Text(f"{message.subtype}: {preview}", style=sys_style))


def render_context_usage(console: Console, usage: dict) -> None:
    table = Table(title="Context Usage")
    table.add_column("Category")
    table.add_column("Tokens", justify="right")
    for cat in usage.get("categories", []):
        table.add_row(str(cat.get("name", "")), str(cat.get("tokens", 0)))
    table.add_row("Total", str(usage.get("totalTokens", 0)))
    table.add_row("Percent", f"{usage.get('percentage', 0):.1f}%")
    console.print(table)
