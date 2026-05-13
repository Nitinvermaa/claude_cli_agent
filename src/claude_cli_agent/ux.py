"""Animated UX: dino mascot loaders."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable, Iterator
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator, TypeVar

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.text import Text

from .console_theme import use_dark_ink

_T = TypeVar("_T")


# Terminal-friendly ASCII dino frames (loop while the model thinks).
DINO_THINK_FRAMES: tuple[str, ...] = (
    "           __\n"
    "          / _)\n"
    "   .-^^^-/ /\n"
    "__/  o o  /\n"
    "<__.|_|-|_|   stomp…",
    "           __\n"
    "          / _)\n"
    "   .-^^^-/ /\n"
    "__/  - -  /\n"
    "<__.|_|-|_|   think…",
    "           __\n"
    "          / _)\n"
    "   .-^^^-/ /\n"
    "__/  ^ ^  /\n"
    "<__.|_|-|_|   chomp…",
    "           __\n"
    "          / _)\n"
    "   .-^^^-/ /\n"
    "__/  o o  /\n"
    "<__.|_|-|_|   done…",
)


def boot_splash(console: Console, *, seconds: float = 1.25) -> None:
    """Sync boot animation: cycling ASCII dino (always visible before welcome)."""
    ink = use_dark_ink()
    border = "#0e7490" if ink else "bright_red"
    deadline = time.time() + seconds
    idx = 0

    def panel(i: int) -> Panel:
        dino = DINO_THINK_FRAMES[i % len(DINO_THINK_FRAMES)]
        if ink:
            inner = Text.assemble(
                (dino + "\n", "#475569"),
                ("Booting cagent…\n", "bold #0f172a"),
                ("Host commands use forward slash: /help, /quit, …\n", "italic #64748b"),
            )
        else:
            inner = Text.assemble(
                (dino + "\n", "dim"),
                ("Booting cagent…\n", "bold cyan"),
                ("Host commands use forward slash: /help, /quit, …\n", "dim italic"),
            )
        return Panel(inner, title="cagent · dino", border_style=border, padding=(0, 1))

    with Live(panel(0), console=console, refresh_per_second=15, transient=True) as live:
        while time.time() < deadline:
            idx += 1
            live.update(panel(idx))
            time.sleep(0.09)


def _caption_style(accent: str) -> str:
    s = (accent or "magenta").strip()
    if s.startswith("#") and len(s) == 7:
        return s
    base = {"black", "red", "green", "yellow", "blue", "magenta", "cyan", "white", "dim"}
    bright = {f"bright_{c}" for c in base if c != "dim"}
    allowed = base | bright
    return f"bold {s}" if s in allowed else "bold bright_magenta"


def _border_style(accent: str) -> str:
    s = (accent or "magenta").strip()
    if s.startswith("#") and len(s) == 7:
        return s
    base = {"black", "red", "green", "yellow", "blue", "magenta", "cyan", "white", "dim"}
    bright = {f"bright_{c}" for c in base if c != "dim"}
    allowed = base | bright
    return s if s in allowed else "bright_magenta"


@asynccontextmanager
async def cartoon_loader(
    console: Console,
    *,
    caption: str,
    accent_color: str = "magenta",
) -> AsyncIterator[None]:
    """Animated thinking loader: ASCII dino + caption (replaces plain spinner)."""
    ink = use_dark_ink()
    cap_style = _caption_style(accent_color)
    border = _border_style(accent_color) if not ink else "#0e7490"
    if ink:
        dino_style = "#475569"
        rule_style = "#94a3b8"
        wait_style = "italic #64748b"
        title = "[bold #0f172a]cagent[/bold #0f172a] [#64748b]·[/#64748b] dino"
        if cap_style.startswith("bold ") and "white" in cap_style:
            cap_style = "bold #0f172a"
    else:
        dino_style = "dim"
        rule_style = "dim"
        wait_style = "dim italic"
        title = "[bold]cagent[/bold] [dim]·[/dim] dino"

    def panel_for(i: int) -> Panel:
        dino = DINO_THINK_FRAMES[i % len(DINO_THINK_FRAMES)]
        body = Text.assemble(
            (dino + "\n", dino_style),
            (caption + "\n", cap_style),
            ("─" * 30 + "\n", rule_style),
            ("Waiting on assistant…", wait_style),
        )
        return Panel(
            body,
            title=title,
            border_style=border,
            padding=(0, 1),
        )

    stop = asyncio.Event()
    idx = 0
    live = Live(panel_for(0), console=console, refresh_per_second=12, transient=True)

    async def tick() -> None:
        nonlocal idx
        while not stop.is_set():
            live.update(panel_for(idx))
            idx += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.12)
            except asyncio.TimeoutError:
                pass

    live.start()
    task = asyncio.create_task(tick())
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        live.stop()


def rich_splash(console: Console) -> None:
    """Short splash; prefer boot_splash() for a longer dino animation."""
    boot_splash(console, seconds=0.75)


def asciimatics_splash(console: Console) -> None:
    try:
        from asciimatics.renderers import FigletText
        from asciimatics.screen import Screen
    except Exception:
        boot_splash(console, seconds=0.6)
        return

    def _run(screen: Screen) -> None:
        title = FigletText("cagent", font="small")
        screen.print_at(title.rendered_text, 2, 2)
        screen.print_at("Production Claude SDK agent", 2, 10)
        screen.print_at("    /\\_/\\   dino", 2, 11)
        screen.refresh()
        screen.wait_for_input(0.65)

    try:
        Screen.wrapper(_run)
    except Exception:
        boot_splash(console, seconds=0.6)


def textual_hint(console: Console) -> None:
    if use_dark_ink():
        console.print(
            "[bold #0f172a]Tip:[/] [#475569]Textual is available for a future full-screen TUI. "
            "If the welcome box still shows old backslash commands, your PATH is using an old install — run[/] "
            "[bold #0369a1]pip install -e .[/] [#475569]in this repo or[/] [bold #0369a1]pipx reinstall cagent[/], "
            "[#475569]then[/] [bold #0369a1]cagent --version[/] [#475569]in the shell (not at the[/] [bold #0f172a]you:[/] [#475569]prompt).[/]"
        )
    else:
        console.print(
            "[bold #e5e7eb]Tip:[/bold #e5e7eb] [#a3b1c6]Textual is available for a future full-screen TUI. "
            "If the welcome box still shows old backslash commands, your PATH is using an old install — "
            "run[/#a3b1c6] [bold #22d3ee]pip install -e .[/bold #22d3ee] [#a3b1c6]in this repo or[/#a3b1c6] "
            "[bold #22d3ee]pipx reinstall cagent[/bold #22d3ee][#a3b1c6], then[/#a3b1c6] "
            "[bold #22d3ee]cagent --version[/bold #22d3ee] [#a3b1c6]in the shell (not at the you: prompt).[/#a3b1c6]"
        )


def track_cartoon(
    console: Console,
    items: Iterable[_T],
    *,
    description: str = "Working",
) -> Iterator[_T]:
    """Rich progress bar with a small dino column (sync iterators)."""
    with Progress(
        TextColumn("[magenta]dino[/magenta]"),
        SpinnerColumn("dots", style="magenta"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(pulse_style="magenta"),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        seq = list(items)
        task_id = progress.add_task(description, total=max(1, len(seq)))
        for item in seq:
            yield item
            progress.advance(task_id)
