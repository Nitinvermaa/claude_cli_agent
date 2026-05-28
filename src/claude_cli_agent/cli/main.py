"""CLI entrypoint for cagent."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from ..backends.registry import BACKEND_IDS, normalize_backend_id
from ..config import load_or_init_config
from ..console_theme import make_console
from ..options_build import AgentMode
from ..scaffolding import ScaffoldRequest, load_web_tech_catalog, refresh_web_tech_catalog, scaffold_project
from ..session import Runtime
from ..tui import CagentTextualApp
from ..usage_tracking import UsageTracker

app = typer.Typer(
    no_args_is_help=False,
    add_completion=False,
    help="Production Claude SDK coding agent CLI with graphify context integration.",
)
graphify_app = typer.Typer(help="Graphify helper commands.")
app.add_typer(graphify_app, name="graphify")
usage_app = typer.Typer(help="Usage/cost telemetry commands.")
app.add_typer(usage_app, name="usage")
console = make_console()


def _parse_mode(value: str) -> AgentMode:
    v = value.lower()
    if v not in {"agent", "plan", "ask", "debug"}:
        raise typer.BadParameter("mode must be one of: agent, plan, ask, debug")
    return v  # type: ignore[return-value]


def _parse_backend(value: str) -> str:
    v = value.lower().strip()
    if v not in BACKEND_IDS:
        raise typer.BadParameter(f"backend must be one of: {', '.join(BACKEND_IDS)}")
    return normalize_backend_id(v)


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Print cagent package version and exit",
            is_flag=True,
            is_eager=True,
        ),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode")] = "agent",
    backend: Annotated[
        str | None,
        typer.Option("--backend", help="Backend: claude_code, independent, copilot_sdk, langchain_copilot"),
    ] = None,
    cwd: Annotated[Path, typer.Option("--cwd", help="Working directory")] = Path.cwd(),
    api_key: Annotated[str | None, typer.Option("--api-key", help="Override API key")] = None,
) -> None:
    """Start interactive REPL when no subcommand is given."""
    if version:
        from .. import __version__

        typer.echo(__version__)
        raise typer.Exit(0)
    if ctx.invoked_subcommand is not None:
        return
    cfg = load_or_init_config(
        console,
        api_key_override=api_key,
        backend_override=_parse_backend(backend) if backend is not None else None,
        cwd=cwd.resolve(),
    )
    runtime = Runtime(config=cfg, cwd=cwd.resolve(), mode=_parse_mode(mode), console=console)
    asyncio.run(runtime.start())


@app.command("new")
def new_project(
    name: Annotated[str, typer.Argument(help="Project folder name")],
    directory: Annotated[Path, typer.Option("--directory", help="Parent directory")] = Path.cwd(),
    mode: Annotated[str, typer.Option("--mode")] = "agent",
    backend: Annotated[str | None, typer.Option("--backend")] = None,
) -> None:
    """Create a new project directory and start cagent there."""
    target = (directory / name).resolve()
    target.mkdir(parents=True, exist_ok=True)
    (target / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    cfg = load_or_init_config(
        console,
        backend_override=_parse_backend(backend) if backend is not None else None,
        cwd=target,
    )
    runtime = Runtime(config=cfg, cwd=target, mode=_parse_mode(mode), console=console)
    asyncio.run(runtime.start())


@app.command("bootstrap")
def bootstrap(
    language: Annotated[str, typer.Option("--language", help="Language: python|javascript|typescript|go|rust|java")],
    name: Annotated[str, typer.Option("--name", help="Project/app name")] = "generated-app",
    framework: Annotated[
        str,
        typer.Option("--framework", help="Framework: react|next|vue|svelte|nuxt|astro|express|fastapi|spring|none"),
    ] = "none",
    voice: Annotated[bool, typer.Option("--voice", help="Include voice API/app stubs")] = False,
    vision: Annotated[bool, typer.Option("--vision", help="Include vision/VLM stubs")] = False,
    cwd: Annotated[Path, typer.Option("--cwd", help="Target parent directory")] = Path.cwd(),
) -> None:
    """Create a language-specific app scaffold with real project files."""
    lang = language.lower().strip()
    fw = framework.lower().strip()
    allowed = {"python", "javascript", "typescript", "go", "rust", "java"}
    allowed_fw = {"react", "next", "vue", "svelte", "nuxt", "astro", "express", "fastapi", "spring", "none"}
    if lang not in allowed:
        raise typer.BadParameter(f"Unsupported language '{language}'. Allowed: {', '.join(sorted(allowed))}")
    if fw not in allowed_fw:
        raise typer.BadParameter(f"Unsupported framework '{framework}'. Allowed: {', '.join(sorted(allowed_fw))}")
    req = ScaffoldRequest(language=lang, name=name, framework=fw, voice_enabled=voice, vision_enabled=vision)  # type: ignore[arg-type]
    target = scaffold_project(cwd.resolve(), req, console)
    console.print(f"[green]Bootstrap complete:[/green] {target}")


@app.command("web-tech")
def web_tech(
    update: Annotated[bool, typer.Option("--update", help="Refresh framework versions from npm")] = False,
) -> None:
    """Show or refresh latest web technology catalog used by scaffolder."""
    catalog = refresh_web_tech_catalog() if update else load_web_tech_catalog()
    action = "Updated" if update else "Current"
    console.print(f"[bold cyan]{action} web tech catalog[/bold cyan]")
    for key, value in sorted(catalog.items()):
        console.print(f"- {key}: {value}")


@app.command("config")
def configure(
    api_key: Annotated[str | None, typer.Option("--api-key")] = None,
    backend: Annotated[str | None, typer.Option("--backend")] = None,
    cwd: Annotated[Path, typer.Option("--cwd", help="Directory used to resolve .env")] = Path.cwd(),
) -> None:
    """Run API key onboarding/update flow."""
    backend_override = _parse_backend(backend) if backend else None
    _ = load_or_init_config(console, api_key_override=api_key, backend_override=backend_override, cwd=cwd.resolve())
    console.print("[green]Configuration complete.[/green]")


@app.command("tui")
def tui() -> None:
    """Launch Textual full-screen UI."""
    CagentTextualApp().run()


@graphify_app.command("update")
def graphify_update(cwd: Annotated[Path, typer.Option("--cwd")] = Path.cwd()) -> None:
    """Run graphify update for current project."""
    try:
        proc = subprocess.run(["graphify", "update", "."], cwd=str(cwd), check=False)
    except FileNotFoundError:
        console.print("[red]graphify command not found.[/red] Install graphify first, then rerun.")
        raise typer.Exit(1) from None
    raise typer.Exit(proc.returncode)


@graphify_app.command("query")
def graphify_query(question: Annotated[str, typer.Argument(help="Graph question")]) -> None:
    """Ask graphify query directly."""
    try:
        proc = subprocess.run(["graphify", "query", question], check=False)
    except FileNotFoundError:
        console.print("[red]graphify command not found.[/red] Install graphify first, then rerun.")
        raise typer.Exit(1) from None
    raise typer.Exit(proc.returncode)


@usage_app.command("report")
def usage_report(
    limit: Annotated[int, typer.Option("--limit", help="Rows to print in terminal table")] = 20,
    output: Annotated[Path | None, typer.Option("--output", help="Output path for HTML dashboard")] = None,
) -> None:
    """Print usage table and export interactive HTML dashboard."""
    cfg = load_or_init_config(console, cwd=Path.cwd())
    tracker = UsageTracker(log_path=Path(cfg.usage_log_path).expanduser(), model=cfg.model)
    tracker.render_terminal_table(console, limit=max(1, limit))
    target = output.expanduser().resolve() if output else Path(cfg.usage_dashboard_path).expanduser().resolve()
    written = tracker.export_html_dashboard(target)
    console.print(f"[green]Wrote dashboard:[/green] {written}")


@app.command("version", help="Print cagent package version (same as --version).")
def cmd_version() -> None:
    from .. import __version__

    typer.echo(__version__)


def app_main() -> None:
    app()


if __name__ == "__main__":
    app_main()
